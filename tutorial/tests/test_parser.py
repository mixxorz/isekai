from pathlib import Path

from tutorial.parsers import CaseStudyParser

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "case_studies"


def load_fixture(filename: str) -> CaseStudyParser:
    html = (FIXTURES_DIR / filename).read_text(encoding="utf-8")
    return CaseStudyParser(html)


class TestCaseStudyParserFixture01:
    """case_study_01.html: reopening-crosswater — newer structure, 4 sections, body images"""

    def setup_method(self):
        self.parser = load_fixture("case_study_01.html")

    def test_get_title(self):
        assert self.parser.get_title() == "Reopening The Crosswater"

    def test_get_category(self):
        assert self.parser.get_category() == "Community Funds"

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Barrhill Community Interest Company"

    def test_get_hero_image_url(self):
        url = self.parser.get_hero_image_url()
        assert url is not None
        assert "sites/default/files" in url

    def test_get_introduction(self):
        intro = self.parser.get_introduction()
        assert "Barrhill" in intro
        assert intro != ""

    def test_get_body_sections_count(self):
        sections = self.parser.get_body_sections()
        assert len(sections) == 4

    def test_get_body_sections_contain_headings(self):
        sections = self.parser.get_body_sections()
        full_text = " ".join(sections)
        assert "The Background" in full_text
        assert "Community Ownership" in full_text
        assert "The Impact" in full_text

    def test_get_body_image_urls(self):
        urls = self.parser.get_body_image_urls()
        assert len(urls) == 2
        assert all("sites/default/files" in u for u in urls)


class TestCaseStudyParserFixture02:
    """case_study_02.html: loch-restocking — newer structure, 2 sections, no body images"""

    def setup_method(self):
        self.parser = load_fixture("case_study_02.html")

    def test_get_title(self):
        assert self.parser.get_title() == "Loch Restocking for Barrhill Angling Club"

    def test_get_hero_image_url_present(self):
        # This page has a hero image
        assert self.parser.get_hero_image_url() is not None

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Barrhill Community Interest Company"

    def test_get_body_sections_count(self):
        sections = self.parser.get_body_sections()
        assert len(sections) == 2

    def test_get_body_image_urls_empty(self):
        assert self.parser.get_body_image_urls() == []

    def test_get_introduction(self):
        intro = self.parser.get_introduction()
        assert "Barrhill Angling Club" in intro


class TestCaseStudyParserFixture03:
    """case_study_03.html: brewing-up-strong-blend-of-skills — Charity Funds, 0 sections"""

    def setup_method(self):
        self.parser = load_fixture("case_study_03.html")

    def test_get_category(self):
        assert self.parser.get_category() == "Charity Funds"

    def test_get_title(self):
        assert self.parser.get_title() == "Brewing up a strong blend of skills"

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Bairdwatson Charitable Trust"

    def test_get_body_sections_empty(self):
        # This page has intro text but no red-brown section headings
        assert self.parser.get_body_sections() == []

    def test_get_introduction(self):
        intro = self.parser.get_introduction()
        assert "Bairdwatson" in intro


class TestCaseStudyParserFixture04:
    """case_study_04.html: watten-school-parent-council — older flat structure, no intro, no fund"""

    def setup_method(self):
        self.parser = load_fixture("case_study_04.html")

    def test_get_title(self):
        assert "Watten" in self.parser.get_title()

    def test_get_body_sections_empty(self):
        # Older flat pages have no p.red-brown section headings
        assert self.parser.get_body_sections() == []

    def test_get_hero_image_url_present(self):
        assert self.parser.get_hero_image_url() is not None

    def test_get_introduction_empty(self):
        # Older pages have no p.text-lead
        assert self.parser.get_introduction() == ""

    def test_get_fund_name_none(self):
        # This page has no Related fund link
        assert self.parser.get_fund_name() is None

    def test_get_category(self):
        assert self.parser.get_category() == "Community Funds"


class TestCaseStudyParserFixture05:
    """case_study_05.html: fischy-music — older flat structure, Charity Funds, no fund"""

    def setup_method(self):
        self.parser = load_fixture("case_study_05.html")

    def test_get_title(self):
        assert "mental health" in self.parser.get_title().lower()

    def test_get_category(self):
        assert self.parser.get_category() == "Charity Funds"

    def test_get_fund_name_none(self):
        assert self.parser.get_fund_name() is None

    def test_get_introduction_empty(self):
        assert self.parser.get_introduction() == ""

    def test_get_body_sections_empty(self):
        assert self.parser.get_body_sections() == []

    def test_get_body_image_urls_empty(self):
        assert self.parser.get_body_image_urls() == []
