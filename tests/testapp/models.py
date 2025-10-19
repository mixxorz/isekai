from typing import TYPE_CHECKING

from django.db import models
from modelcluster.fields import ParentalManyToManyField
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from isekai.contrib.wagtail.transformers import DocumentTransformer, ImageTransformer
from isekai.extractors import BaseExtractor, HTTPExtractor
from isekai.loaders import ModelLoader
from isekai.miners import HTMLImageMiner
from isekai.models import AbstractResource
from isekai.seeders import CSVSeeder, SitemapSeeder
from isekai.transformers import BaseTransformer
from isekai.types import Spec, TextResource


class FooBarExtractor(BaseExtractor):
    def extract(self, key, metadata=None):
        if not key.type == "foo":
            return None

        return TextResource(mime_type="foo/bar", text="foo bar data", metadata={})


class FooBarTransformer(BaseTransformer):
    def transform(self, key, resource):
        if resource.mime_type != "foo/bar":
            return None

        return Spec(
            content_type="auth.User",
            attributes={
                "username": "foobar_user",
                "email": "foo@bar.com",
            },
        )


# Test models for ModelLoader testing
class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    bio = models.JSONField(blank=True, null=True)

    if TYPE_CHECKING:
        authorprofile: "AuthorProfile"

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#000000")  # hex color

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.name


class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, blank=True)
    metadata = models.JSONField(blank=True, null=True)
    published_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.title


class AuthorProfile(models.Model):
    author = models.OneToOneField(Author, on_delete=models.CASCADE)
    website = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=200, blank=True)
    settings = models.JSONField(blank=True, null=True)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return f"{self.author.name}'s Profile"


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    page_count = models.IntegerField()  # Required integer field

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.title


class ClusterableArticle(ClusterableModel):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    tags = ParentalManyToManyField(Tag, blank=True)
    metadata = models.JSONField(blank=True, null=True)
    published_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.title


class ConcreteResource(AbstractResource):
    seeders = [
        CSVSeeder(csv_filename="tests/files/test_data.csv"),
        SitemapSeeder(sitemap_url="https://example.com/sitemap.xml"),
        SitemapSeeder(sitemap_url="https://example.com/jp/sitemap.xml"),
    ]
    extractors = [
        HTTPExtractor(),
        FooBarExtractor(),
    ]
    miners = [HTMLImageMiner(allowed_domains=["*"])]
    transformers = [
        ImageTransformer(),
        DocumentTransformer(),
        FooBarTransformer(),
    ]
    loaders = [
        ModelLoader(),
    ]

    class Meta:
        app_label = "testapp"
        verbose_name = "Concrete Resource"
        verbose_name_plural = "Concrete Resources"


# Wagtail page models for testing
class ReportIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.title


class ReportPage(Page):
    intro = RichTextField(blank=True)
    body = RichTextField(blank=True)
    date = models.DateField("Report date", null=True, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
        FieldPanel("date"),
    ]

    class Meta:
        app_label = "testapp"

    def __str__(self):
        return self.title
