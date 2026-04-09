import html
import re
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query, Request

from fields.article import ArticleCreate, ArticlePublish, ArticleUpdate
from models.article import SystemArticle
from models.article_meta import SystemArticleCategory, SystemArticleTag
from utils.pagination import PageParams, get_page_params
from utils.response import ResponseUtil


articleAPI = APIRouter(prefix="/article", tags=["article"])


def strip_html_content(content: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_tag_ids(tag_ids: list[str] | None) -> list[str]:
    if not tag_ids:
        return []
    normalized = [str(item).strip() for item in tag_ids if str(item).strip()]
    return list(dict.fromkeys(normalized))


async def resolve_taxonomy_payload(payload: dict) -> dict:
    data = dict(payload)

    if "category_id" in data:
        category_id = (data.get("category_id") or "").strip() or None
        data["category_id"] = category_id
        data["category_name"] = None

        if category_id:
            category_rows = await SystemArticleCategory.filter(
                id=category_id, is_del=False
            ).values("id", "name")
            category = category_rows[0] if category_rows else None
            if not category:
                raise ValueError("Article category does not exist")
            data["category_name"] = category["name"]

    if "tag_ids" in data:
        tag_ids = normalize_tag_ids(data.get("tag_ids"))
        data["tag_ids"] = tag_ids
        data["tag_names"] = []

        if tag_ids:
            tag_rows = await SystemArticleTag.filter(id__in=tag_ids, is_del=False).values("id", "name")
            tag_map = {str(item["id"]): item["name"] for item in tag_rows}
            if len(tag_map) != len(tag_ids):
                raise ValueError("One or more article tags do not exist")
            data["tag_names"] = [tag_map[item] for item in tag_ids]

    return data


async def build_article_payload(payload: dict, current_article: dict | None = None) -> dict:
    data = dict(payload)
    if "content" in data and data["content"] is not None:
        data["content_text"] = strip_html_content(data["content"])

    data = await resolve_taxonomy_payload(data)

    next_status = data.get("status")
    if next_status is not None:
        if next_status == 1:
            published_at = current_article.get("published_at") if current_article else None
            data["published_at"] = published_at or datetime.now()
        else:
            data["published_at"] = None

    return data


@articleAPI.get("/list", summary="Article list")
async def list_articles(
    title: str | None = Query(default=None),
    status: int | None = Query(default=None),
    category_id: str | None = Query(default=None),
    page: PageParams = Depends(get_page_params),
):
    queryset = SystemArticle.filter(is_del=False)
    if title:
        queryset = queryset.filter(title__icontains=title)
    if status is not None:
        queryset = queryset.filter(status=status)
    if category_id:
        queryset = queryset.filter(category_id=category_id)

    total = await queryset.count()
    records = (
        await queryset.order_by("-is_top", "sort", "-published_at", "-created_at")
        .offset(page.offset)
        .limit(page.size)
        .values(
            "id",
            "title",
            "summary",
            "cover",
            "content_text",
            "category_id",
            "category_name",
            "tag_ids",
            "tag_names",
            "status",
            "published_at",
            "author_id",
            "author_name",
            "sort",
            "is_top",
            "view_count",
            "remark",
            "created_at",
            "updated_at",
        )
    )
    return ResponseUtil.success(
        data={
            "records": records,
            "total": total,
            "current": page.current,
            "size": page.size,
        }
    )


@articleAPI.get("/info/{article_id}", summary="Article info")
async def article_info(article_id: str):
    rows = await SystemArticle.filter(id=article_id, is_del=False).values()
    if not rows:
        return ResponseUtil.failure(msg="Article does not exist")
    return ResponseUtil.success(data=rows[0])


@articleAPI.post("/add", summary="Add article")
async def add_article(payload: ArticleCreate, request: Request):
    try:
        data = await build_article_payload(payload.model_dump())
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))

    user = getattr(request.state, "user", {}) or {}
    data["author_id"] = user.get("sub")
    data["author_name"] = user.get("username")
    created = await SystemArticle.create(**data)
    return ResponseUtil.success(msg="Created successfully", data={"id": str(created.id)})


@articleAPI.put("/update/{article_id}", summary="Update article")
async def update_article(article_id: str, payload: ArticleUpdate, request: Request):
    rows = await SystemArticle.filter(id=article_id, is_del=False).values()
    article = rows[0] if rows else None
    if not article:
        return ResponseUtil.failure(msg="Article does not exist")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return ResponseUtil.failure(msg="No fields to update")

    try:
        data = await build_article_payload(data, article)
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))

    user = getattr(request.state, "user", {}) or {}
    if user.get("sub"):
        data["author_id"] = user.get("sub")
    if user.get("username"):
        data["author_name"] = user.get("username")

    await SystemArticle.filter(id=article_id, is_del=False).update(**data)
    return ResponseUtil.success(msg="Updated successfully")


@articleAPI.delete("/delete/{article_id}", summary="Delete article")
async def delete_article(article_id: str):
    exists = await SystemArticle.filter(id=article_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="Article does not exist")
    await SystemArticle.filter(id=article_id, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="Deleted successfully")


@articleAPI.post("/publish/{article_id}", summary="Publish article")
async def publish_article(article_id: str, payload: ArticlePublish = Body(default=ArticlePublish())):
    rows = await SystemArticle.filter(id=article_id, is_del=False).values()
    article = rows[0] if rows else None
    if not article:
        return ResponseUtil.failure(msg="Article does not exist")

    data = await build_article_payload({"status": payload.status}, article)
    await SystemArticle.filter(id=article_id, is_del=False).update(**data)
    return ResponseUtil.success(msg="Operation succeeded")
