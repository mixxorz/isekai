from isekai.miners import BaseMiner
from isekai.types import BlobResource, Key, MinedResource, TextResource
from tutorial.parsers import CaseStudyParser


class CaseStudyMiner(BaseMiner):
    """Mines image resources from a case study page."""

    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        if key.type != "url":
            return []
        if not isinstance(resource, TextResource):
            return []

        parser = CaseStudyParser(resource.text)
        mined: list[MinedResource] = []

        hero_url = parser.get_hero_image_url()
        if hero_url:
            mined.append(
                MinedResource(key=Key(type="url", value=hero_url), metadata={})
            )

        for image_url in parser.get_body_image_urls():
            mined.append(
                MinedResource(key=Key(type="url", value=image_url), metadata={})
            )

        return mined
