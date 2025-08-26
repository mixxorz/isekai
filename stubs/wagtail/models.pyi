from typing import Any, ClassVar, Self

from django.db import models
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet

class PageManager(BaseManager[Any]):
    def specific(self) -> QuerySet[Any]: ...

class Page(models.Model):
    title: str
    slug: str
    depth: int
    content_panels: ClassVar[list[Any]]

    def get_parent(self) -> Page: ...
    def get_children(self) -> PageManager: ...
    def add_child(self, *, instance: Page) -> Any: ...
    def move(self, target: Page, pos: str = ...) -> None: ...
    @classmethod
    def get_root_nodes(cls) -> QuerySet[Page]: ...
    @property
    def specific(self) -> Self: ...

class Site(models.Model):
    root_page: Page
