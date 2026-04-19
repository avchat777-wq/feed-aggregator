"""Sources CRUD API + diagnostics + JK stats."""

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_admin
from app.models.source import Source
from app.models.object import Object
from app.models.jk_synonym import JkSynonym
from app.parsers import get_parser
from app.scheduler.scheduler import run_preflight
from app.schemas.schemas import (
    SourceCreate, SourceUpdate, SourceResponse,
    SourceJkStatsResponse, JkStatItem, DiagnosticsResult,
)

router = APIRouter(prefix="/api/sources", tags=["sources"])


# ──────────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Source).order_by(Source.id))
    return result.scalars().all()


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    source = Source(**data.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    data: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)

    await db.flush()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)


# ──────────────────────────────────────────────────────────────────────────────
# Test parse (preview)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{source_id}/test")
async def test_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Test-fetch a source and return parse preview (first 10 objects)."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if not source.url:
        raise HTTPException(status_code=400, detail="Source has no URL")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(source.url)
            resp.raise_for_status()
            content = resp.content
    except Exception as e:
        return {"success": False, "error": str(e), "objects": []}

    parser_cls = get_parser(source.type)
    parser = parser_cls({
        "name": source.name,
        "developer_name": source.developer_name,
        "mapping_config": source.mapping_config,
        "phone_override": source.phone_override,
    })
    raw_objects = parser.parse(content)

    # Collect unique JK names found in this feed
    jk_names = sorted({o.jk_name for o in raw_objects if o.jk_name})

    preview = [
        {
            "source_object_id": obj.source_object_id,
            "jk_name": obj.jk_name,
            "house_name": obj.house_name,
            "flat_number": obj.flat_number,
            "floor": obj.floor,
            "rooms": obj.rooms,
            "total_area": obj.total_area,
            "price": obj.price,
            "phone": obj.phone,
            "status": obj.status,
        }
        for obj in raw_objects[:10]
    ]

    return {
        "success": True,
        "total_parsed": len(raw_objects),
        "jk_names_found": jk_names,
        "errors": parser.errors[:10],
        "preview": preview,
    }


@router.get("/{source_id}/raw-tags")
async def raw_xml_tags(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Fetch feed and return all XML tag names + sample values from first object.

    Useful for diagnosing which field names a feed uses, so you can update
    FIELD_CANDIDATES in the parser if fields are missing.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.url:
        raise HTTPException(status_code=400, detail="Source has no URL")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(source.url)
            resp.raise_for_status()
            content = resp.content
    except Exception as e:
        return {"error": str(e)}

    from lxml import etree as _etree

    try:
        root = _etree.fromstring(content)
    except _etree.XMLSyntaxError:
        # Try with recovery for slightly broken feeds
        parser_lxml = _etree.XMLParser(recover=True)
        root = _etree.fromstring(content, parser=parser_lxml)

    # Find first object element (covers DomClick, Avito, Yandex, custom formats)
    first_obj = None
    for tag in (
        "Ad", "ad",                                          # Avito
        "object", "Object", "offer", "Offer",               # DomClick / Yandex
        "flat", "Flat", "item", "Item", "apartment",        # misc
        "realty", "Realty", "listing", "Listing",
    ):
        els = root.findall(f".//{tag}")
        if els:
            first_obj = els[0]
            break

    if first_obj is None:
        return {
            "root_tag": root.tag,
            "root_children": [c.tag for c in root],
            "error": "No object/offer/flat elements found",
        }

    # Collect all tags and their values from first object
    fields: dict[str, str] = {}

    def collect(elem, prefix=""):
        tag = elem.tag if not prefix else f"{prefix}/{elem.tag}"
        val = (elem.text or "").strip()
        if val:
            fields[tag] = val[:80]
        for attr, av in elem.attrib.items():
            fields[f"{tag}[@{attr}]"] = av[:80]
        if prefix.count("/") < 2:
            for child in elem:
                collect(child, tag)

    collect(first_obj)

    # ── Collect parent chain (for detecting JK name on <complex> level) ──────
    # Build a parent map so we can walk up from first_obj
    parent_map: dict = {}
    for elem in root.iter():
        for child in elem:
            parent_map[child] = elem

    parent_context: list[dict] = []
    cur = first_obj
    depth = 0
    while cur in parent_map and depth < 5:
        cur = parent_map[cur]
        if cur is root:
            break
        entry: dict = {"tag": cur.tag, "attrs": {}, "direct_text_children": {}}
        for attr, av in cur.attrib.items():
            entry["attrs"][attr] = av[:80]
        for child in cur:
            if child.text and child.text.strip() and not list(child):
                entry["direct_text_children"][child.tag] = child.text.strip()[:80]
        parent_context.append(entry)
        depth += 1

    # Root element attributes / direct non-object children with text
    root_info: dict = {"tag": root.tag, "attrs": {}, "direct_text_children": {}}
    for attr, av in root.attrib.items():
        root_info["attrs"][attr] = av[:80]
    for child in root:
        if child.tag != first_obj.tag and child.text and child.text.strip() and not list(child):
            root_info["direct_text_children"][child.tag] = child.text.strip()[:80]

    return {
        "root_tag": root.tag,
        "object_tag": first_obj.tag,
        "total_objects": len(root.findall(f".//{first_obj.tag}")),
        "root_info": root_info,
        "parent_context": parent_context,
        "fields": fields,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pre-flight diagnostics
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{source_id}/diagnostics", response_model=DiagnosticsResult)
async def run_diagnostics(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Run 5 pre-flight checks on the source URL and return results."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    t0 = time.time()
    preflight = await run_preflight(source)
    duration_ms = int((time.time() - t0) * 1000)

    # Persist new status
    source.status = "ok" if preflight.passed else "error"
    await db.commit()

    return DiagnosticsResult(
        source_id=source.id,
        source_name=source.name,
        passed=preflight.passed,
        checks=preflight.checks,
        duration_ms=duration_ms,
    )


# ──────────────────────────────────────────────────────────────────────────────
# JK stats per source
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{source_id}/jk-stats", response_model=SourceJkStatsResponse)
async def source_jk_stats(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Return object count and price stats grouped by JK for this source."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    stmt = (
        select(
            Object.jk_name,
            func.count(Object.id).label("cnt"),
            func.avg(Object.price).label("avg_price"),
            func.min(Object.price).label("min_price"),
            func.max(Object.price).label("max_price"),
        )
        .where(Object.source_id == source_id, Object.status == "active")
        .group_by(Object.jk_name)
        .order_by(Object.jk_name)
    )
    rows = (await db.execute(stmt)).all()

    return SourceJkStatsResponse(
        source_id=source.id,
        source_name=source.name,
        jk_stats=[
            JkStatItem(
                jk_name=row.jk_name,
                object_count=row.cnt,
                avg_price=int(row.avg_price or 0),
                min_price=row.min_price or 0,
                max_price=row.max_price or 0,
            )
            for row in rows
        ],
    )


# ──────────────────────────────────────────────────────────────────────────────
# JK Synonyms CRUD  (global, not per-source)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/synonyms/list")
async def list_synonyms(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(JkSynonym).order_by(JkSynonym.normalized_name))
    syns = result.scalars().all()
    return [
        {"id": s.id, "raw_name": s.raw_name, "normalized_name": s.normalized_name}
        for s in syns
    ]


@router.post("/synonyms/add", status_code=201)
async def add_synonym(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Add a JK synonym mapping.  Body: {raw_name, normalized_name}"""
    raw = (body.get("raw_name") or "").strip()
    norm = (body.get("normalized_name") or "").strip()
    if not raw or not norm:
        raise HTTPException(status_code=400, detail="raw_name and normalized_name required")

    # Store raw_name lowercase for case-insensitive lookup
    existing = await db.execute(
        select(JkSynonym).where(JkSynonym.raw_name == raw.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Synonym for this raw_name already exists")

    syn = JkSynonym(raw_name=raw.lower(), normalized_name=norm)
    db.add(syn)
    await db.commit()
    await db.refresh(syn)
    return {"id": syn.id, "raw_name": syn.raw_name, "normalized_name": syn.normalized_name}


@router.delete("/synonyms/{synonym_id}", status_code=204)
async def delete_synonym(
    synonym_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(JkSynonym).where(JkSynonym.id == synonym_id))
    syn = result.scalar_one_or_none()
    if not syn:
        raise HTTPException(status_code=404, detail="Synonym not found")
    await db.delete(syn)
    await db.commit()
