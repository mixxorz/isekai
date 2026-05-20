from django.conf import settings

from isekai.transformers import BaseTransformer
from isekai.types import BlobRef, BlobResource, Key, Spec, TextResource
from tutorial.parsers import CaseStudyParser


class CaseStudyTransformer(BaseTransformer):
    """Transforms an extracted case study HTML page into a CaseStudyPage Spec."""

    def transform(self, key: Key, resource: TextResource | BlobResource) -> Spec | None:
        if key.type != "url":
            return None
        if not isinstance(resource, TextResource):
            return None

        parser = CaseStudyParser(resource.text)
        title = parser.get_title()
        if not title:
            return None

        attributes: dict = {
            "title": title,
            "category": parser.get_category(),
            "fund_name": parser.get_fund_name() or "",
            "introduction": parser.get_introduction(),
            "body": [
                {"type": "section", "value": section}
                for section in parser.get_body_sections()
            ],
            "__wagtail_parent_page": settings.CASE_STUDIES_PARENT_PAGE_ID,
        }

        hero_url = parser.get_hero_image_url()
        if hero_url:
            attributes["hero_image"] = BlobRef(Key(type="url", value=hero_url))

        return Spec(
            content_type="tutorial.casestudypage",
            attributes=attributes,
        )
