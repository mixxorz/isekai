from bs4 import BeautifulSoup, Tag


class CaseStudyParser:
    """Extracts structured data from a Foundation Scotland case study HTML page."""

    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "html.parser")

    def get_title(self) -> str:
        tag = self.soup.find("h1", class_="heading-primary")
        if tag is None:
            return ""
        return tag.get_text(strip=True)

    def get_category(self) -> str:
        for ul in self.soup.find_all("ul", class_="list-meta"):
            for li in ul.find_all("li"):
                if "Category" in li.get_text():
                    link = li.find("a")
                    if link:
                        return link.get_text(strip=True)
        return ""

    def get_fund_name(self) -> str | None:
        for ul in self.soup.find_all("ul", class_="list-meta"):
            for li in ul.find_all("li"):
                if "Related fund" in li.get_text():
                    link = li.find("a")
                    if link:
                        return link.get_text(strip=True)
        return None

    def get_hero_image_url(self) -> str | None:
        # The hero figure has the "wide" class among its figure classes
        hero_fig = self.soup.find("figure", class_="wide")
        if hero_fig is None:
            return None
        img = hero_fig.find("img")
        if img is None:
            return None
        src = img.get("src")
        return str(src) if src else None

    def get_introduction(self) -> str:
        # Newer pages have p.text-lead; older pages have no dedicated intro element
        tag = self.soup.find("p", class_="text-lead")
        if tag is None:
            return ""
        return tag.get_text(strip=True)

    def get_body_sections(self) -> list[str]:
        """
        Returns body sections as a list of HTML strings.

        Newer pages use p.red-brown as section headings (without text-lead class).
        Each section runs from one p.red-brown to the next.
        Older flat pages have no p.red-brown elements and return an empty list.
        """
        all_tags: list[Tag] = []
        for div in self.soup.find_all("div", class_="editor"):
            for child in div.children:
                if isinstance(child, Tag):
                    all_tags.append(child)

        sections: list[str] = []
        current: list[Tag] = []
        in_section = False

        for tag in all_tags:
            classes = tag.get("class") or []
            is_heading = (
                tag.name == "p"
                and "red-brown" in classes
                and "text-lead" not in classes
            )
            if is_heading:
                if in_section and current:
                    sections.append("".join(str(t) for t in current))
                current = [tag]
                in_section = True
            elif in_section:
                current.append(tag)

        if in_section and current:
            sections.append("".join(str(t) for t in current))

        return sections

    def get_body_image_urls(self) -> list[str]:
        """Returns image src values found inside div.editor (body content, not hero)."""
        urls = []
        for div in self.soup.find_all("div", class_="editor"):
            for img in div.find_all("img"):
                src = img.get("src")
                if src:
                    urls.append(str(src))
        return urls
