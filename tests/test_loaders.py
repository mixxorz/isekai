from typing import overload

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Model
from django.utils import timezone
from freezegun import freeze_time
from wagtail.images.models import Image

from isekai.loaders import ModelLoader
from isekai.pipelines import get_django_pipeline
from isekai.types import (
    BlobRef,
    FileProxy,
    InMemoryFileProxy,
    Key,
    ModelRef,
    ResourceRef,
    Spec,
    ref,
)
from tests.testapp.models import (
    Article,
    Author,
    AuthorProfile,
    Book,
    ClusterableArticle,
    ConcreteResource,
    Tag,
)


@pytest.mark.django_db
@pytest.mark.database_backend
class TestModelLoader:
    def test_load_spec_with_blob(self):
        @overload
        def resolver(ref: BlobRef) -> FileProxy: ...
        @overload
        def resolver(ref: ResourceRef) -> int | str: ...
        @overload
        def resolver(ref: ModelRef) -> Model: ...

        def resolver(
            ref: ResourceRef | BlobRef | ModelRef,
        ) -> FileProxy | int | str | Model:
            if isinstance(ref, BlobRef):
                with open("tests/files/blue_square.jpg", "rb") as f:
                    return InMemoryFileProxy(f.read())
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        key = Key(type="url", value="https://example.com/blue_square.jpg")
        spec = Spec(
            content_type="wagtailimages.Image",
            attributes={
                "title": "blue_square.jpg",
                "file": BlobRef(key),
                "description": "A sample image",
            },
        )

        objects = loader.load([(key, spec)], resolver)

        image = objects[0][1]
        assert isinstance(image, Image)
        assert image.title == "blue_square.jpg"
        assert image.description == "A sample image"

        with open("tests/files/blue_square.jpg", "rb") as f:
            expected_content = f.read()

        # Read from the saved file to compare content
        with image.file.open() as saved_file:
            assert saved_file.read() == expected_content

    def test_load_spec_with_document_blob(self):
        @overload
        def resolver(ref: BlobRef) -> FileProxy: ...
        @overload
        def resolver(ref: ResourceRef) -> int | str: ...
        @overload
        def resolver(ref: ModelRef) -> Model: ...

        def resolver(
            ref: ResourceRef | BlobRef | ModelRef,
        ) -> FileProxy | int | str | Model:
            if isinstance(ref, BlobRef):
                text_content = b"This is a sample document for testing."
                return InMemoryFileProxy(text_content)
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        key = Key(type="url", value="https://example.com/sample.txt")
        spec = Spec(
            content_type="wagtaildocs.Document",
            attributes={
                "title": "sample.txt",
                "file": BlobRef(key),
            },
        )

        objects = loader.load([(key, spec)], resolver)

        from wagtail.documents.models import Document

        document = objects[0][1]
        assert isinstance(document, Document)
        assert document.title == "sample.txt"

        expected_content = b"This is a sample document for testing."

        # Read from the saved file to compare content
        with document.file.open() as saved_file:
            assert saved_file.read() == expected_content

    def test_load_simple_model(self):
        """Test loading a simple model without relationships."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        key = Key(type="author", value="jane_doe")
        spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "bio": {"expertise": "Django", "years_experience": 5},
            },
        )

        objects = loader.load([(key, spec)], resolver)

        assert len(objects) == 1
        author = objects[0][1]
        assert isinstance(author, Author)
        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.bio == {"expertise": "Django", "years_experience": 5}

    def test_load_with_foreign_key_reference(self):
        """Test loading models with foreign key relationships."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="john_smith")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "John Smith",
                "email": "john@example.com",
            },
        )

        # Create article spec that references the author
        article_key = Key(type="article", value="test_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Test Article",
                "content": "This is a test article.",
                "author_id": ResourceRef(author_key).pk,
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article in results
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        assert author.name == "John Smith"
        assert article.title == "Test Article"
        assert article.author == author

    def test_load_with_many_to_many_relationships(self):
        """Test loading models with many-to-many relationships."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create tag specs
        tag1_key = Key(type="tag", value="python")
        tag1_spec = Spec(
            content_type="testapp.Tag",
            attributes={
                "name": "Python",
                "color": "#3776ab",
            },
        )

        tag2_key = Key(type="tag", value="django")
        tag2_spec = Spec(
            content_type="testapp.Tag",
            attributes={
                "name": "Django",
                "color": "#092e20",
            },
        )

        # Create author spec
        author_key = Key(type="author", value="alice")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Alice Developer",
                "email": "alice@example.com",
            },
        )

        # Create article spec with M2M relationships
        article_key = Key(type="article", value="python_django_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Python and Django Best Practices",
                "content": "Here are some best practices...",
                "author_id": ResourceRef(author_key).pk,
                "tags": [
                    ResourceRef(tag1_key),
                    ResourceRef(tag2_key),
                ],
            },
        )

        objects = loader.load(
            [
                (tag1_key, tag1_spec),
                (tag2_key, tag2_spec),
                (author_key, author_spec),
                (article_key, article_spec),
            ],
            resolver,
        )

        assert len(objects) == 4

        # Find objects in results
        tags = [obj[1] for obj in objects if isinstance(obj[1], Tag)]
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        assert len(tags) == 2
        assert article.author == author

        # Check M2M relationships
        article_tags = list(article.tags.all())
        assert len(article_tags) == 2
        tag_names = {tag.name for tag in article_tags}
        assert tag_names == {"Python", "Django"}

    def test_load_with_m2m_resourceref(self):
        """Test loading M2M relationships with ResourceRef."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="m2m_modelref_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "M2M ModelRef Author",
                "email": "m2m_modelref@example.com",
            },
        )

        # Create tag specs
        tag1_key = Key(type="tag", value="modelref_tag1")
        tag1_spec = Spec(
            content_type="testapp.Tag",
            attributes={"name": "ModelRef Tag 1"},
        )

        tag2_key = Key(type="tag", value="modelref_tag2")
        tag2_spec = Spec(
            content_type="testapp.Tag",
            attributes={"name": "ModelRef Tag 2"},
        )

        # Create article spec with M2M relationships using ModelRef
        article_key = Key(type="article", value="modelref_m2m_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Article with ModelRef M2M",
                "content": "Testing ModelRef in M2M relationships.",
                "author_id": ResourceRef(author_key).pk,
                "tags": [
                    ResourceRef(tag1_key),  # ResourceRef in M2M
                    ResourceRef(tag2_key),  # ResourceRef in M2M
                ],
            },
        )

        loader.load(
            [
                (tag1_key, tag1_spec),
                (tag2_key, tag2_spec),
                (author_key, author_spec),
                (article_key, article_spec),
            ],
            resolver,
        )

        # Fetch from database to verify persistence
        author = Author.objects.get(email="m2m_modelref@example.com")
        article = Article.objects.get(title="Article with ModelRef M2M")
        tags = Tag.objects.filter(
            name__in=["ModelRef Tag 1", "ModelRef Tag 2"]
        ).order_by("name")

        assert len(tags) == 2
        assert article.author == author

        # Check M2M relationships from database
        article_tags = list(article.tags.all().order_by("name"))
        assert len(article_tags) == 2
        tag_names = {tag.name for tag in article_tags}
        assert tag_names == {"ModelRef Tag 1", "ModelRef Tag 2"}

    def test_load_with_m2m_resourceref_parental(self):
        """Test loading M2M relationships with ResourceRef using ParentalManyToManyField."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="m2m_parental_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "M2M Parental Author",
                "email": "m2m_parental@example.com",
            },
        )

        # Create tag specs
        tag1_key = Key(type="tag", value="parental_tag1")
        tag1_spec = Spec(
            content_type="testapp.Tag",
            attributes={"name": "Parental Tag 1"},
        )

        tag2_key = Key(type="tag", value="parental_tag2")
        tag2_spec = Spec(
            content_type="testapp.Tag",
            attributes={"name": "Parental Tag 2"},
        )

        # Create article spec with M2M relationships using ResourceRef
        article_key = Key(type="article", value="parental_m2m_article")
        article_spec = Spec(
            content_type="testapp.ClusterableArticle",
            attributes={
                "title": "Article with Parental M2M",
                "content": "Testing ParentalManyToManyField with ResourceRef.",
                "author_id": ResourceRef(author_key).pk,
                "tags": [
                    ResourceRef(tag1_key),  # ResourceRef in ParentalM2M
                    ResourceRef(tag2_key),  # ResourceRef in ParentalM2M
                ],
            },
        )

        loader.load(
            [
                (tag1_key, tag1_spec),
                (tag2_key, tag2_spec),
                (author_key, author_spec),
                (article_key, article_spec),
            ],
            resolver,
        )

        # Fetch objects from database to verify
        author = Author.objects.get(email="m2m_parental@example.com")
        article = ClusterableArticle.objects.get(title="Article with Parental M2M")
        tags = Tag.objects.filter(
            name__in=["Parental Tag 1", "Parental Tag 2"]
        ).order_by("name")

        assert len(tags) == 2
        assert article.author == author

        # Check M2M relationships from database
        article_tags = list(article.tags.all().order_by("name"))
        assert len(article_tags) == 2
        tag_names = {tag.name for tag in article_tags}
        assert tag_names == {"Parental Tag 1", "Parental Tag 2"}

    def test_load_with_m2m_internal_refs(self):
        """Test loading M2M relationships with ResourceRef to objects in same batch."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="mixed_m2m_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Mixed M2M Author",
                "email": "mixed_m2m@example.com",
            },
        )

        # Create tag specs
        tag1_key = Key(type="tag", value="mixed_tag1")
        tag1_spec = Spec(
            content_type="testapp.Tag",
            attributes={"name": "Mixed Tag 1"},
        )

        tag2_key = Key(type="tag", value="mixed_tag2")
        tag2_spec = Spec(
            content_type="testapp.Tag",
            attributes={"name": "Mixed Tag 2"},
        )

        # Create article spec with ResourceRef in M2M (both internal)
        article_key = Key(type="article", value="mixed_m2m_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Article with M2M Internal References",
                "content": "Testing ResourceRef in M2M.",
                "author_id": ResourceRef(author_key).pk,
                "tags": [
                    ResourceRef(tag1_key),  # ResourceRef in M2M
                    ResourceRef(tag2_key),  # ResourceRef in M2M
                ],
            },
        )

        objects = loader.load(
            [
                (tag1_key, tag1_spec),
                (tag2_key, tag2_spec),
                (author_key, author_spec),
                (article_key, article_spec),
            ],
            resolver,
        )

        assert len(objects) == 4

        # Check M2M relationships
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))
        article_tags = list(article.tags.all())
        assert len(article_tags) == 2
        tag_names = {tag.name for tag in article_tags}
        assert tag_names == {"Mixed Tag 1", "Mixed Tag 2"}

    def test_load_with_json_field_references(self):
        """Test loading models with references in JSON fields."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create mentor spec
        mentor_key = Key(type="author", value="carol_mentor")
        mentor_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Carol Mentor",
                "email": "carol@example.com",
            },
        )

        # Create author spec with JSON field reference
        author_key = Key(type="author", value="bob_writer")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Bob Writer",
                "email": "bob@example.com",
                "bio": {
                    "description": "Experienced writer",
                    "favorite_topics": ["Python", "Django"],
                    "mentor": ResourceRef(mentor_key).pk,
                },
            },
        )

        objects = loader.load(
            [(mentor_key, mentor_spec), (author_key, author_spec)], resolver
        )

        assert len(objects) == 2

        # Find objects
        mentor = next(
            obj[1] for obj in objects if getattr(obj[1], "name", None) == "Carol Mentor"
        )
        author = next(
            obj[1] for obj in objects if getattr(obj[1], "name", None) == "Bob Writer"
        )

        # Check JSON field reference resolution
        assert isinstance(author, Author)
        author_bio = author.bio
        assert author_bio is not None
        assert author_bio["mentor"] == mentor.pk
        assert author_bio["description"] == "Experienced writer"
        assert author_bio["favorite_topics"] == ["Python", "Django"]

    def test_load_with_external_reference(self):
        """Test loading models that reference existing objects via resolver."""
        # First create an existing author in the database
        existing_author = Author.objects.create(
            name="Existing Author",
            email="existing@example.com",
        )

        def resolver(ref):
            if ref.key.type == "author" and ref.key.value == "existing_author":
                return existing_author.pk
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        # Create article that references the existing author
        article_key = Key(type="article", value="external_ref_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Article with External Author",
                "content": "This article references an existing author.",
                "author_id": ResourceRef(
                    Key(type="author", value="existing_author")
                ).pk,
            },
        )

        objects = loader.load([(article_key, article_spec)], resolver)

        assert len(objects) == 1
        article = objects[0][1]
        assert isinstance(article, Article)
        assert article.title == "Article with External Author"
        assert article.author == existing_author
        assert article.author.name == "Existing Author"

    def test_load_with_circular_references(self):
        """Test loading models with circular references."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author and article that reference each other
        author_key = Key(type="author", value="circular_author")
        article_key = Key(type="article", value="circular_article")

        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Circular Author",
                "email": "circular@example.com",
                "bio": {
                    "featured_article": ResourceRef(
                        article_key
                    ).pk,  # Author references article in JSON
                },
            },
        )

        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Circular Article",
                "content": "This article references its author.",
                "author_id": ResourceRef(
                    author_key
                ).pk,  # Article references author via FK
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Check circular references are resolved correctly
        assert article.author == author
        author_bio = author.bio
        assert author_bio is not None
        assert author_bio["featured_article"] == article.pk

    def test_load_with_self_reference(self):
        """Test loading models with self-references."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create two authors where one references the other as mentor
        mentor_key = Key(type="author", value="mentor_author")
        student_key = Key(type="author", value="student_author")

        mentor_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Mentor Author",
                "email": "mentor@example.com",
            },
        )

        student_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Student Author",
                "email": "student@example.com",
                "bio": {
                    "mentor": ResourceRef(
                        mentor_key
                    ).pk,  # Self-reference via JSON field
                },
            },
        )

        objects = loader.load(
            [(mentor_key, mentor_spec), (student_key, student_spec)], resolver
        )

        assert len(objects) == 2
        mentor = next(
            obj[1]
            for obj in objects
            if getattr(obj[1], "name", None) == "Mentor Author"
        )
        student = next(
            obj[1]
            for obj in objects
            if getattr(obj[1], "name", None) == "Student Author"
        )

        assert isinstance(student, Author)
        student_bio = student.bio
        assert student_bio is not None
        assert student_bio["mentor"] == mentor.pk

    def test_load_with_mixed_internal_external_m2m(self):
        """Test M2M fields with both internal and external references."""
        # Create existing tag in database
        existing_tag = Tag.objects.create(name="Existing Tag", color="#ff0000")

        def resolver(ref):
            if ref.key.type == "tag" and ref.key.value == "existing_tag":
                return existing_tag.pk
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        # Create new tag and author
        new_tag_key = Key(type="tag", value="new_tag")
        author_key = Key(type="author", value="mixed_author")
        article_key = Key(type="article", value="mixed_article")

        new_tag_spec = Spec(
            content_type="testapp.Tag",
            attributes={
                "name": "New Tag",
                "color": "#00ff00",
            },
        )

        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Mixed Author",
                "email": "mixed@example.com",
            },
        )

        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Mixed M2M Article",
                "content": "This article has mixed tag references.",
                "author_id": ResourceRef(author_key).pk,
                "tags": [
                    ResourceRef(new_tag_key),  # Internal reference to new tag
                    ResourceRef(
                        Key(type="tag", value="existing_tag")
                    ),  # External reference to existing tag
                ],
            },
        )

        objects = loader.load(
            [
                (new_tag_key, new_tag_spec),
                (author_key, author_spec),
                (article_key, article_spec),
            ],
            resolver,
        )

        assert len(objects) == 3
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Check M2M relationships include both internal and external refs
        article_tags = list(article.tags.all())
        assert len(article_tags) == 2

        tag_names = {tag.name for tag in article_tags}
        assert tag_names == {"New Tag", "Existing Tag"}

    def test_load_with_empty_and_null_values(self):
        """Test loading with empty lists, null values, and empty objects."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        author_key = Key(type="author", value="empty_author")
        article_key = Key(type="article", value="empty_article")

        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Empty Author",
                "email": "empty@example.com",
                "bio": {},  # Empty JSON object
            },
        )

        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Empty Article",
                "content": "This article has empty relationships.",
                "author_id": ResourceRef(author_key).pk,
                # Note: Empty M2M list [] would be handled by M2M phase, not included here
                "metadata": None,  # Explicit null value
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        assert author.bio == {}
        assert article.author == author
        assert list(article.tags.all()) == []  # M2M should be empty by default
        assert article.metadata is None

    def test_load_with_onetoone_field(self):
        """Test loading models with OneToOne field relationships."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author and profile with OneToOne relationship
        author_key = Key(type="author", value="profile_author")
        profile_key = Key(type="profile", value="author_profile")

        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Profile Author",
                "email": "profile@example.com",
            },
        )

        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(author_key).pk,  # OneToOne reference
                "website": "https://example.com",
                "twitter_handle": "@profile_author",
                "settings": {"theme": "dark", "notifications": True},
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        profile = next(obj[1] for obj in objects if isinstance(obj[1], AuthorProfile))

        # Check OneToOne relationship
        assert profile.author == author
        assert author.authorprofile == profile  # Reverse relationship
        assert profile.website == "https://example.com"
        assert profile.twitter_handle == "@profile_author"
        assert profile.settings == {"theme": "dark", "notifications": True}

    def test_load_with_external_onetoone_reference(self):
        """Test OneToOne field with external reference via resolver."""
        # Create existing author in database
        existing_author = Author.objects.create(
            name="Existing OneToOne Author",
            email="existing_oto@example.com",
        )

        def resolver(ref):
            if ref.key.type == "author" and ref.key.value == "existing_oto_author":
                return existing_author.pk
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        profile_key = Key(type="profile", value="external_oto_profile")
        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(
                    Key(type="author", value="existing_oto_author")
                ).pk,
                "website": "https://external.example.com",
                "settings": {"external": True},
            },
        )

        objects = loader.load([(profile_key, profile_spec)], resolver)

        assert len(objects) == 1
        profile = objects[0][1]
        assert isinstance(profile, AuthorProfile)
        assert profile.author == existing_author
        assert profile.website == "https://external.example.com"
        assert profile.settings == {"external": True}

    def test_load_with_onetoone_json_reference(self):
        """Test OneToOne relationship with JSON field containing references."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create two authors
        author1_key = Key(type="author", value="json_author1")
        author2_key = Key(type="author", value="json_author2")
        profile_key = Key(type="profile", value="json_profile")

        author1_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "JSON Author 1",
                "email": "json1@example.com",
            },
        )

        author2_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "JSON Author 2",
                "email": "json2@example.com",
            },
        )

        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(author1_key).pk,
                "website": "https://jsontest.example.com",
                "settings": {
                    "preferred_collaborator": ResourceRef(
                        author2_key
                    ).pk,  # Ref in JSON
                    "theme": "light",
                },
            },
        )

        objects = loader.load(
            [
                (author1_key, author1_spec),
                (author2_key, author2_spec),
                (profile_key, profile_spec),
            ],
            resolver,
        )

        assert len(objects) == 3
        author1 = next(
            obj[1]
            for obj in objects
            if getattr(obj[1], "name", None) == "JSON Author 1"
        )
        author2 = next(
            obj[1]
            for obj in objects
            if getattr(obj[1], "name", None) == "JSON Author 2"
        )
        profile = next(obj[1] for obj in objects if isinstance(obj[1], AuthorProfile))

        # Check OneToOne and JSON reference resolution
        assert profile.author == author1
        profile_settings = profile.settings
        assert profile_settings is not None
        assert profile_settings["preferred_collaborator"] == author2.pk
        assert profile_settings["theme"] == "light"

    def test_load_with_foreign_key_id_field(self):
        """Test loading models with foreign key relationships using _id field."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="id_field_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "ID Field Author",
                "email": "idfield@example.com",
            },
        )

        # Create article spec that references the author using author_id
        article_key = Key(type="article", value="id_field_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "ID Field Article",
                "content": "This article uses author_id field.",
                "author_id": ResourceRef(author_key).pk,  # Using _id suffix
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article in results
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        assert author.name == "ID Field Author"
        assert article.title == "ID Field Article"
        assert article.author == author

    def test_load_with_onetoone_id_field(self):
        """Test loading OneToOne relationships using _id field."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="oto_id_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "OTO ID Author",
                "email": "otoid@example.com",
            },
        )

        # Create profile spec that references the author using author_id
        profile_key = Key(type="profile", value="oto_id_profile")
        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(
                    author_key
                ).pk,  # Using _id suffix for OneToOne
                "website": "https://otoid.example.com",
                "settings": {"test": True},
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        profile = next(obj[1] for obj in objects if isinstance(obj[1], AuthorProfile))

        # Check OneToOne relationship
        assert profile.author == author
        assert author.authorprofile == profile  # Reverse relationship
        assert profile.website == "https://otoid.example.com"

    def test_load_empty_specs(self):
        """Test that loading empty specs returns empty list."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()
        objects = loader.load([], resolver)

        assert objects == []

    def test_load_with_resourceref_for_required_integer_field(self):
        """Test that using ResourceRef for a required non-FK integer field works correctly."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="book_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Book Author",
                "email": "bookauthor@example.com",
            },
        )

        # Create another author whose pk (an integer) we'll use for page_count
        page_count_source_key = Key(type="author", value="page_count_source")
        page_count_source_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Page Count Source",
                "email": "pagesource@example.com",
            },
        )

        # Create book spec that uses ResourceRef.pk for page_count (required integer field)
        # Note: This is a non-FK integer field, not a ForeignKey
        book_key = Key(type="book", value="test_book")
        book_spec = Spec(
            content_type="testapp.Book",
            attributes={
                "title": "Test Book",
                "author_id": ResourceRef(author_key).pk,  # FK field
                # This should work: ResourceRef.pk for a required IntegerField (not FK)
                # A temp value will be set, then resolved to the actual pk value
                "page_count": ResourceRef(
                    page_count_source_key
                ).pk,  # Regular integer field
            },
        )

        objects = loader.load(
            [
                (author_key, author_spec),
                (page_count_source_key, page_count_source_spec),
                (book_key, book_spec),
            ],
            resolver,
        )

        assert len(objects) == 3

        # Find the objects
        book_author = next(
            obj[1]
            for obj in objects
            if isinstance(obj[1], Author) and obj[1].name == "Book Author"
        )
        page_count_source = next(
            obj[1]
            for obj in objects
            if isinstance(obj[1], Author) and obj[1].name == "Page Count Source"
        )
        book = next(obj[1] for obj in objects if isinstance(obj[1], Book))

        # Verify the book was created correctly
        assert book.title == "Test Book"
        assert book.author == book_author
        # The page_count should be the pk of page_count_source (an integer)
        assert book.page_count == page_count_source.pk
        assert isinstance(book.page_count, int)

    def test_load_with_arbitrary_attribute_paths(self):
        """Test that ResourceRef with arbitrary attribute paths like .name, .email work."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="jane_smith")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Jane Smith",
                "email": "jane@example.com",
            },
        )

        # Create article spec that uses various author attributes
        article_key = Key(type="article", value="attr_path_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": ResourceRef(author_key).name,  # Use author's name as title
                "content": ResourceRef(
                    author_key
                ).email,  # Use author's email as content
                "author_id": ResourceRef(author_key).pk,  # Use author's pk for FK
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article in results
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Verify the attribute paths were resolved correctly
        assert author.name == "Jane Smith"
        assert author.email == "jane@example.com"
        assert article.title == "Jane Smith"  # Should be author's name
        assert article.content == "jane@example.com"  # Should be author's email
        assert article.author == author  # FK should be resolved correctly

    def test_load_with_string_ref_single_resourceref(self):
        """Test loading with a single ResourceRef embedded in a string field."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="string_ref_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Jane Smith",
                "email": "jane@example.com",
            },
        )

        # Create article spec with string that contains ResourceRef
        article_key = Key(type="article", value="string_ref_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": f"Article by {ref(ResourceRef(author_key).name)}",
                "content": "Some content",
                "author_id": ResourceRef(author_key).pk,
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article in results
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Verify the string ref was resolved
        assert author.name == "Jane Smith"
        assert article.title == "Article by Jane Smith"  # Ref should be resolved
        assert article.author == author

    def test_load_with_string_ref_multiple_resourcerefs(self):
        """Test loading with multiple ResourceRefs embedded in a single string field."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="multi_ref_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Bob Writer",
                "email": "bob@example.com",
            },
        )

        # Create article spec with string containing multiple refs
        article_key = Key(type="article", value="multi_ref_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": f"Contact {ref(ResourceRef(author_key).name)} at {ref(ResourceRef(author_key).email)}",
                "content": "Article content",
                "author_id": ResourceRef(author_key).pk,
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Verify both refs were resolved in the string
        assert author.name == "Bob Writer"
        assert author.email == "bob@example.com"
        assert article.title == "Contact Bob Writer at bob@example.com"
        assert article.author == author

    def test_load_with_string_ref_modelref(self):
        """Test loading with ModelRef embedded in string field."""
        # Create existing author in database
        existing_author = Author.objects.create(
            name="Existing Author",
            email="existing@example.com",
        )

        @overload
        def resolver(ref: BlobRef) -> FileProxy: ...
        @overload
        def resolver(ref: ResourceRef) -> int | str: ...
        @overload
        def resolver(ref: ModelRef) -> int | str | Model: ...

        def resolver(
            ref: ResourceRef | BlobRef | ModelRef,
        ) -> FileProxy | int | str | Model:
            if isinstance(ref, ModelRef):
                if (
                    ref.ref_content_type == "testapp.Author"
                    and ref.ref_lookup_kwargs.get("pk") == str(existing_author.pk)
                ):
                    # Resolve ModelRef with attribute path
                    obj = existing_author
                    for attr in ref.ref_attr_path:
                        obj = getattr(obj, attr)
                    return obj
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        # Create article spec with string that contains ModelRef to existing author
        article_key = Key(type="article", value="modelref_string_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": f"By {ref(ModelRef('testapp.Author', pk=existing_author.pk).name)}",
                "content": "Article content",
                "author_id": existing_author.pk,
            },
        )

        objects = loader.load([(article_key, article_spec)], resolver)

        assert len(objects) == 1
        article = objects[0][1]
        assert isinstance(article, Article)
        assert article.title == "By Existing Author"  # ModelRef should be resolved
        assert article.author == existing_author

    def test_load_with_string_ref_chained_attributes(self):
        """Test loading with ResourceRef that has chained attribute access in string."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec with short name
        author_key = Key(type="author", value="chained_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Alice",
                "email": "chained@example.com",
            },
        )

        # Create profile spec
        profile_key = Key(type="profile", value="chained_profile")
        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(author_key).pk,
                "website": "https://chained.example.com",
                "twitter_handle": f"@{ref(ResourceRef(author_key).name)}",
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)], resolver
        )

        assert len(objects) == 2

        # Find objects
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        profile = next(obj[1] for obj in objects if isinstance(obj[1], AuthorProfile))

        # Verify chained attribute access was resolved
        assert profile.twitter_handle == "@Alice"
        assert profile.author == author

    def test_load_with_string_ref_no_refs(self):
        """Test that strings without refs are not modified."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="no_ref_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "No Ref Author",
                "email": "noref@example.com",
            },
        )

        # Create article spec with normal strings (no refs)
        article_key = Key(type="article", value="no_ref_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Normal Title Without Refs",
                "content": "This is normal content without any references",
                "author_id": ResourceRef(author_key).pk,
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find article
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Verify strings are unchanged
        assert article.title == "Normal Title Without Refs"
        assert article.content == "This is normal content without any references"

    def test_load_with_string_ref_different_string_field_types(self):
        """Test that string ref resolution works with different string field types."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec with short name to avoid varchar length issues
        author_key = Key(type="author", value="field_type_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Alice",
                "email": f"contact-{ref(ResourceRef(author_key).name)}@example.com",  # EmailField with ref
            },
        )

        # Create profile spec
        profile_key = Key(type="profile", value="field_type_profile")
        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(author_key).pk,
                "website": f"https://{ref(ResourceRef(author_key).name)}.example.com",  # URLField with ref
                "twitter_handle": f"@{ref(ResourceRef(author_key).name)}",  # CharField with ref
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)], resolver
        )

        assert len(objects) == 2

        # Find objects
        author = next(obj[1] for obj in objects if isinstance(obj[1], Author))
        profile = next(obj[1] for obj in objects if isinstance(obj[1], AuthorProfile))

        # Verify different field types all resolved refs correctly
        assert author.name == "Alice"
        # Email field should have the ref resolved
        assert author.email == "contact-Alice@example.com"
        # URLField should have ref resolved
        assert profile.website == "https://Alice.example.com"
        # CharField should have ref resolved
        assert profile.twitter_handle == "@Alice"

    def test_load_with_string_ref_external_resourceref(self):
        """Test string ref resolution with external ResourceRef resolved via resolver."""
        # Create existing author in database
        existing_author = Author.objects.create(
            name="External String Ref Author",
            email="external@example.com",
        )

        @overload
        def resolver(ref: BlobRef) -> FileProxy: ...
        @overload
        def resolver(ref: ResourceRef) -> int | str | Model: ...
        @overload
        def resolver(ref: ModelRef) -> int | str | Model: ...

        def resolver(
            ref: ResourceRef | BlobRef | ModelRef,
        ) -> FileProxy | int | str | Model:
            if isinstance(ref, ResourceRef):
                if ref.key.type == "author" and ref.key.value == "external_author":
                    # Resolve external ResourceRef with attribute path
                    obj = existing_author
                    for attr in ref.ref_attr_path:
                        obj = getattr(obj, attr)
                    return obj
            raise AssertionError(f"Unexpected ref: {ref}")

        loader = ModelLoader()

        # Create article that references external author in string
        article_key = Key(type="article", value="external_string_article")
        external_author_key = Key(type="author", value="external_author")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": f"Written by {ref(ResourceRef(external_author_key).name)}",
                "content": "Article content",
                "author_id": existing_author.pk,
            },
        )

        objects = loader.load([(article_key, article_spec)], resolver)

        assert len(objects) == 1
        article = objects[0][1]
        assert isinstance(article, Article)
        assert article.title == "Written by External String Ref Author"
        assert article.author == existing_author

    def test_load_with_string_ref_mixed_with_literal_text(self):
        """Test that refs in strings can be mixed with literal text, punctuation, etc."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create two authors
        author1_key = Key(type="author", value="author1")
        author1_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Alice",
                "email": "alice@example.com",
            },
        )

        author2_key = Key(type="author", value="author2")
        author2_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "Bob",
                "email": "bob@example.com",
            },
        )

        # Create article with complex string mixing refs and literals
        article_key = Key(type="article", value="mixed_text_article")
        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": f"Co-authored by {ref(ResourceRef(author1_key).name)} & {ref(ResourceRef(author2_key).name)}!",
                "content": f"Contact: {ref(ResourceRef(author1_key).email)} or {ref(ResourceRef(author2_key).email)}.",
                "author_id": ResourceRef(author1_key).pk,
            },
        )

        objects = loader.load(
            [
                (author1_key, author1_spec),
                (author2_key, author2_spec),
                (article_key, article_spec),
            ],
            resolver,
        )

        assert len(objects) == 3

        # Find article
        article = next(obj[1] for obj in objects if isinstance(obj[1], Article))

        # Verify complex string resolution
        assert article.title == "Co-authored by Alice & Bob!"
        assert article.content == "Contact: alice@example.com or bob@example.com."

    def test_load_with_string_ref_in_json_field(self):
        """Test loading with ResourceRef embedded in string inside JSON field."""

        def resolver(ref):
            raise AssertionError(f"Resolver should not be called, got ref: {ref}")

        loader = ModelLoader()

        # Create author spec
        author_key = Key(type="author", value="json_string_author")
        author_spec = Spec(
            content_type="testapp.Author",
            attributes={
                "name": "JSON String Author",
                "email": "jsonstring@example.com",
            },
        )

        # Create profile spec with JSON field containing string with embedded ref
        profile_key = Key(type="profile", value="json_string_profile")
        profile_spec = Spec(
            content_type="testapp.AuthorProfile",
            attributes={
                "author_id": ResourceRef(author_key).pk,
                "website": "https://jsonstring.example.com",
                "settings": {
                    "description": f"Profile for {ref(ResourceRef(author_key).name)}",
                    "contact_email": f"contact-{ref(ResourceRef(author_key).name)}@example.com",
                    "theme": "dark",
                },
            },
        )

        loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)],
            resolver,
        )

        # Fetch from database to verify
        author = Author.objects.get(email="jsonstring@example.com")
        profile = AuthorProfile.objects.get(author=author)

        # Verify JSON field has resolved string refs
        assert profile.settings is not None
        assert profile.settings["description"] == "Profile for JSON String Author"
        assert (
            profile.settings["contact_email"]
            == "contact-JSON String Author@example.com"
        )
        assert profile.settings["theme"] == "dark"


@pytest.mark.django_db
@pytest.mark.database_backend
class TestLoad:
    def test_load_simple_object(self):
        content_type = ContentType.objects.get(app_label="testapp", model="author")

        ConcreteResource.objects.create(
            key="author:jane_doe",
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=content_type,
            target_spec={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "bio": {"expertise": "Django", "years_experience": 5},
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        author = Author.objects.get()
        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.bio == {"expertise": "Django", "years_experience": 5}

    def test_load_object_with_dependencies(self):
        author_resource = ConcreteResource.objects.create(
            key="author:jane_doe",
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "bio": {"expertise": "Django", "years_experience": 5},
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        article_resource = ConcreteResource.objects.create(
            key="article:test_article",
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Test Article",
                "content": "This is a test article.",
                "author_id": str(ResourceRef(Key.from_string(author_resource.key)).pk),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        author = Author.objects.get()
        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.bio == {"expertise": "Django", "years_experience": 5}

        article = Article.objects.get()
        assert article.title == "Test Article"
        assert article.content == "This is a test article."
        assert article.author == author

        # Check resources are marked as loaded
        author_resource.refresh_from_db()
        assert author_resource.target_object == author
        assert author_resource.status == ConcreteResource.Status.LOADED
        assert author_resource.loaded_at == now

        article_resource.refresh_from_db()
        assert article_resource.target_object == article
        assert article_resource.status == ConcreteResource.Status.LOADED
        assert article_resource.loaded_at == now

    def test_load_object_with_circular_dependencies(self):
        author_key = Key(type="author", value="jane_doe")
        article_key = Key(type="article", value="test_article")

        author_resource = ConcreteResource.objects.create(
            key=str(author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "bio": {"featured_articles": [str(ResourceRef(article_key).pk)]},
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        article_resource = ConcreteResource.objects.create(
            key=str(article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Test Article",
                "content": "This is a test article.",
                "author_id": str(ResourceRef(Key.from_string(author_resource.key)).pk),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        author_resource.dependencies.add(article_resource)
        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        author = Author.objects.get()
        article = Article.objects.get()

        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.bio == {"featured_articles": [article.pk]}

        assert article.title == "Test Article"
        assert article.content == "This is a test article."
        assert article.author == author

        # Check resources are marked as loaded
        author_resource.refresh_from_db()
        assert author_resource.target_object == author
        assert author_resource.status == ConcreteResource.Status.LOADED
        assert author_resource.loaded_at == now

        article_resource.refresh_from_db()
        assert article_resource.target_object == article
        assert article_resource.status == ConcreteResource.Status.LOADED
        assert article_resource.loaded_at == now

    def test_load_object_depends_on_existing_object(self):
        author_key = Key(type="author", value="jane_doe")
        article_key = Key(type="article", value="test_article")

        # Author is already loaded
        author = Author.objects.create(
            name="Jane Doe",
            email="jane@example.com",
        )
        author_resource = ConcreteResource.objects.create(
            key=str(author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_object_id=author.pk,
            target_spec={
                "name": "Jane Doe",
                "email": "jane@example.com",
            },
            status=ConcreteResource.Status.LOADED,
        )

        # Article depends on the existing author
        article_resource = ConcreteResource.objects.create(
            key=str(article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Test Article",
                "content": "This is a test article.",
                "author_id": str(ResourceRef(Key.from_string(author_resource.key)).pk),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        article = Article.objects.get()

        # Check resources are marked as loaded
        article_resource.refresh_from_db()
        assert article_resource.target_object == article
        assert article_resource.status == ConcreteResource.Status.LOADED
        assert article_resource.loaded_at == now

    def test_load_comprehensive_dependency_scenarios(self):
        """Test load function robustness with mixed dependency scenarios."""

        # Define all keys
        independent_author_key = Key(type="author", value="independent_author")
        independent_tag_key = Key(type="tag", value="independent_tag")

        circular_author_key = Key(type="author", value="circular_author")
        circular_article_key = Key(type="article", value="circular_article")

        chain_author_key = Key(type="author", value="chain_author")
        chain_article_key = Key(type="article", value="chain_article")
        chain_profile_key = Key(type="profile", value="chain_profile")

        # 1. Independent resources (no dependencies)
        independent_author = ConcreteResource.objects.create(
            key=str(independent_author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Independent Author",
                "email": "independent@example.com",
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        independent_tag = ConcreteResource.objects.create(
            key=str(independent_tag_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="tag"
            ),
            target_spec={
                "name": "Independent Tag",
                "color": "#ffffff",
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # 2. Circular dependencies
        circular_author = ConcreteResource.objects.create(
            key=str(circular_author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Circular Author",
                "email": "circular@example.com",
                "bio": {"featured_article": str(ResourceRef(circular_article_key).pk)},
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        circular_article = ConcreteResource.objects.create(
            key=str(circular_article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Circular Article",
                "content": "This article has circular dependencies.",
                "author_id": str(ResourceRef(circular_author_key).pk),
                "tags": [
                    str(ResourceRef(independent_tag_key).pk)
                ],  # Reference independent resource
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        circular_author.dependencies.add(circular_article)
        circular_article.dependencies.add(circular_author, independent_tag)

        # 3. Chain dependencies (A -> B -> C)
        chain_author = ConcreteResource.objects.create(
            key=str(chain_author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Chain Author",
                "email": "chain@example.com",
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        chain_article = ConcreteResource.objects.create(
            key=str(chain_article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Chain Article",
                "content": "This article is part of a dependency chain.",
                "author_id": str(ResourceRef(chain_author_key).pk),
                "tags": [
                    str(ResourceRef(independent_tag_key).pk)
                ],  # Cross-reference to independent
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        chain_profile = ConcreteResource.objects.create(
            key=str(chain_profile_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="authorprofile"
            ),
            target_spec={
                "author_id": str(ResourceRef(chain_author_key).pk),
                "website": "https://chain.example.com",
                "settings": {
                    "featured_article": str(ResourceRef(chain_article_key).pk),
                    "collaborator": str(ResourceRef(independent_author_key).pk),
                },
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Set up dependency chains
        chain_article.dependencies.add(chain_author, independent_tag)
        chain_profile.dependencies.add(chain_author, chain_article, independent_author)

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Verify all objects were created correctly
        authors = Author.objects.all().order_by("name")
        articles = Article.objects.all().order_by("title")
        tags = Tag.objects.all()
        profiles = AuthorProfile.objects.all()

        assert len(authors) == 3
        assert len(articles) == 2
        assert len(tags) == 1
        assert len(profiles) == 1

        # Verify independent resources
        independent_author_obj = authors.get(name="Independent Author")
        independent_tag_obj = tags.get(name="Independent Tag")

        # Verify circular dependencies are resolved
        circular_author_obj = authors.get(name="Circular Author")
        circular_article_obj = articles.get(title="Circular Article")

        assert circular_article_obj.author == circular_author_obj
        assert circular_author_obj.bio is not None
        assert circular_author_obj.bio["featured_article"] == circular_article_obj.pk
        assert list(circular_article_obj.tags.all()) == [independent_tag_obj]

        # Verify chain dependencies
        chain_author_obj = authors.get(name="Chain Author")
        chain_article_obj = articles.get(title="Chain Article")
        chain_profile_obj = profiles.get()

        assert chain_article_obj.author == chain_author_obj
        assert chain_profile_obj.author == chain_author_obj
        assert list(chain_article_obj.tags.all()) == [independent_tag_obj]
        assert chain_profile_obj.settings is not None
        assert chain_profile_obj.settings["featured_article"] == chain_article_obj.pk
        assert chain_profile_obj.settings["collaborator"] == independent_author_obj.pk

        # Verify all resources are marked as loaded
        for resource in ConcreteResource.objects.all():
            resource.refresh_from_db()
            assert resource.status == ConcreteResource.Status.LOADED
            assert resource.loaded_at == now
            assert resource.target_object_id is not None

    def test_load_with_missing_external_reference(self):
        """Test load function behavior when external reference cannot be resolved."""
        article_key = Key(type="article", value="missing_ref_article")

        # Create resource with reference to non-existent author
        ConcreteResource.objects.create(
            key=str(article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Article with Missing Author",
                "content": "This article references a non-existent author.",
                "author_id": str(
                    ResourceRef(Key(type="author", value="nonexistent_author")).pk
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Resource should have failed to load and have error recorded
        resource = ConcreteResource.objects.get()
        resource.refresh_from_db()
        assert (
            resource.status == ConcreteResource.Status.TRANSFORMED
        )  # Status unchanged
        assert resource.last_error is not None
        assert "Unable to resolve reference: " in resource.last_error
        assert not resource.target_object_id

        # No Article objects should have been created
        assert Article.objects.count() == 0

    def test_load_with_invalid_spec_attributes(self):
        """Test load function behavior when spec has invalid attributes."""
        author_key = Key(type="author", value="invalid_spec_author")

        ConcreteResource.objects.create(
            key=str(author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Invalid Author",
                "email": "invalid@example.com",
                "nonexistent_field": "this should cause an error",  # Invalid field
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Resource should have failed to load
        resource = ConcreteResource.objects.get()
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.TRANSFORMED
        assert resource.last_error is not None
        assert not resource.target_object_id

        # No Author objects should have been created
        assert Author.objects.count() == 0

    def test_load_stops_on_dependency_failure(self):
        """Test that load operation stops when a dependency fails, preventing cascade failures."""
        author_key = Key(type="author", value="failing_author")
        article_key = Key(type="article", value="dependent_article")

        # Create author resource with invalid spec that will fail
        author_resource = ConcreteResource.objects.create(
            key=str(author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Failing Author",
                "email": "failing@example.com",
                "nonexistent_field": "this will cause failure",  # This will cause the node to fail
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Create article resource that depends on the failing author
        article_resource = ConcreteResource.objects.create(
            key=str(article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Dependent Article",
                "content": "This article depends on the failing author.",
                "author_id": str(ResourceRef(author_key).pk),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Set up dependency
        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Both resources should remain unchanged
        author_resource.refresh_from_db()
        article_resource.refresh_from_db()

        # Author should have failed with error recorded
        assert author_resource.status == ConcreteResource.Status.TRANSFORMED
        assert author_resource.last_error is not None
        assert not author_resource.target_object_id

        # Article should remain unprocessed (no error recorded, still TRANSFORMED)
        # because processing stopped after author failed
        assert article_resource.status == ConcreteResource.Status.TRANSFORMED
        assert not article_resource.last_error
        assert not article_resource.target_object_id

        # No database objects should have been created
        assert Author.objects.count() == 0
        assert Article.objects.count() == 0

    def test_load_with_blob_ref(self):
        """Test loading resources with BlobRef (like images) works correctly."""
        image_key = Key(type="image", value="test_image")

        # Create resource with BlobRef in target_spec
        resource = ConcreteResource.objects.create(
            key=str(image_key),
            mime_type="image/jpeg",
            data_type="binary",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="wagtailimages", model="image"
            ),
            target_spec={
                "title": "blue_square.jpg",
                "file": str(BlobRef(image_key)),
                "description": "A test image with BlobRef",
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Add real image data to the resource
        with open("tests/files/blue_square.jpg", "rb") as f:
            image_data = f.read()
        resource.blob_data.save("blue_square.jpg", ContentFile(image_data))

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Verify image was created correctly
        image = Image.objects.get()
        assert image.title == "blue_square.jpg"
        assert image.description == "A test image with BlobRef"

        # Verify the file content matches the real image data
        with image.file.open() as saved_file:
            assert saved_file.read() == image_data

        # Verify resource is marked as loaded
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.LOADED
        assert resource.loaded_at == now
        assert resource.target_object == image

    def test_load_with_resource_ref_in_serialized_spec(self):
        """Test loading resources with ResourceRef in serialized target_spec."""
        # Create author first
        author_key = Key(type="author", value="test_author")
        author_resource = ConcreteResource.objects.create(
            key=str(author_key),
            mime_type="application/json",
            data_type="text",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "John Doe",
                "email": "john@example.com",
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Create article that references the author with ResourceRef
        article_key = Key(type="article", value="test_article")
        article_resource = ConcreteResource.objects.create(
            key=str(article_key),
            mime_type="application/json",
            data_type="text",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Test Article with ResourceRef",
                "content": "Article content here",
                "author": str(
                    ResourceRef(author_key)
                ),  # Using ResourceRef for internal ref
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Verify both objects were created correctly
        author = Author.objects.get()
        assert author.name == "John Doe"
        assert author.email == "john@example.com"

        article = Article.objects.get()
        assert article.title == "Test Article with ResourceRef"
        assert article.content == "Article content here"
        assert article.author == author  # ResourceRef resolved to author instance

        # Verify resources are marked as loaded
        author_resource.refresh_from_db()
        article_resource.refresh_from_db()
        assert author_resource.status == ConcreteResource.Status.LOADED
        assert article_resource.status == ConcreteResource.Status.LOADED
        assert author_resource.loaded_at == now
        assert article_resource.loaded_at == now
        assert author_resource.target_object == author
        assert article_resource.target_object == article

    def test_load_is_idempotent(self):
        """Test that running load multiple times doesn't re-load already loaded resources."""
        content_type = ContentType.objects.get(app_label="testapp", model="author")

        resource = ConcreteResource.objects.create(
            key="author:idempotent_test",
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=content_type,
            target_spec={
                "name": "Idempotent Author",
                "email": "idempotent@example.com",
                "bio": {"test": "data"},
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # First load operation
        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Verify resource was loaded
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.LOADED
        assert resource.loaded_at == now
        assert resource.target_object_id is not None
        original_target_object_id = resource.target_object_id

        # Verify Author was created
        author = Author.objects.get()
        assert author.name == "Idempotent Author"
        assert author.email == "idempotent@example.com"
        assert author.bio == {"test": "data"}
        assert str(author.pk) == resource.target_object_id

        # Second load operation - should be no-op
        later = now + timezone.timedelta(hours=1)
        with freeze_time(later):
            pipeline = get_django_pipeline()
            pipeline.load()

        # Verify resource state unchanged
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.LOADED
        assert resource.loaded_at == now  # Timestamp should not change
        assert (
            resource.target_object_id == original_target_object_id
        )  # Same target object

        # Verify no duplicate Authors were created
        assert Author.objects.count() == 1
        updated_author = Author.objects.get()
        assert updated_author.pk == author.pk  # Same object
        assert updated_author.name == "Idempotent Author"
        assert updated_author.email == "idempotent@example.com"
        assert updated_author.bio == {"test": "data"}

    def test_load_skips_resources_with_unready_dependencies_and_cascade_effect(self):
        """Test that resources with unready dependencies are skipped, including cascading effect."""
        # Create a chain of dependencies: base_author -> dependent_article -> dependent_profile
        base_author_key = Key(type="author", value="base_author")
        dependent_article_key = Key(type="article", value="dependent_article")
        dependent_profile_key = Key(type="profile", value="dependent_profile")

        # Also create an independent resource that should be loaded successfully
        independent_author_key = Key(type="author", value="independent_author")

        # Create base author resource in MINED status (not ready for loading)
        base_author_resource = ConcreteResource.objects.create(
            key=str(base_author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Base Author",
                "email": "base@example.com",
            },
            status=ConcreteResource.Status.MINED,  # NOT TRANSFORMED - dependency not ready
        )

        # Create article resource in TRANSFORMED status that depends on the unready author
        dependent_article_resource = ConcreteResource.objects.create(
            key=str(dependent_article_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="article"
            ),
            target_spec={
                "title": "Dependent Article",
                "content": "This article depends on the unready author.",
                "author_id": str(ResourceRef(base_author_key).pk),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        dependent_article_resource.dependencies.add(base_author_resource)

        # Create profile resource in TRANSFORMED status that depends on the article
        dependent_profile_resource = ConcreteResource.objects.create(
            key=str(dependent_profile_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="authorprofile"
            ),
            target_spec={
                "author_id": str(ResourceRef(base_author_key).pk),
                "website": "https://dependent.example.com",
                "settings": {
                    "featured_article": str(ResourceRef(dependent_article_key).pk),
                },
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        dependent_profile_resource.dependencies.add(
            base_author_resource, dependent_article_resource
        )

        # Create an independent resource that should be loaded successfully
        independent_author_resource = ConcreteResource.objects.create(
            key=str(independent_author_key),
            mime_type="application/json",
            data_type="text",
            text_data="does not matter",
            metadata={},
            target_content_type=ContentType.objects.get(
                app_label="testapp", model="author"
            ),
            target_spec={
                "name": "Independent Author",
                "email": "independent@example.com",
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            result = pipeline.load()

        # Verify that only the independent resource was processed and loaded
        independent_author_resource.refresh_from_db()
        dependent_article_resource.refresh_from_db()
        dependent_profile_resource.refresh_from_db()
        base_author_resource.refresh_from_db()

        # Independent resource should be loaded successfully
        assert independent_author_resource.status == ConcreteResource.Status.LOADED
        assert independent_author_resource.target_object_id is not None
        assert independent_author_resource.loaded_at == now

        # Resources with unready dependencies should remain TRANSFORMED (not processed)
        assert dependent_article_resource.status == ConcreteResource.Status.TRANSFORMED
        assert not dependent_article_resource.target_object_id
        assert dependent_article_resource.loaded_at is None
        assert not dependent_article_resource.last_error

        # Resources that depend on unready resources should also remain TRANSFORMED
        assert dependent_profile_resource.status == ConcreteResource.Status.TRANSFORMED
        assert not dependent_profile_resource.target_object_id
        assert dependent_profile_resource.loaded_at is None
        assert not dependent_profile_resource.last_error

        # The base resource should remain unchanged in MINED status
        assert base_author_resource.status == ConcreteResource.Status.MINED
        assert not base_author_resource.target_object_id
        assert base_author_resource.loaded_at is None

        # Verify only one Author object was created (the independent one)
        assert Author.objects.count() == 1
        independent_author = Author.objects.get()
        assert independent_author.name == "Independent Author"
        assert independent_author.email == "independent@example.com"

        # Verify no Article or AuthorProfile objects were created
        assert Article.objects.count() == 0
        assert AuthorProfile.objects.count() == 0

        # Verify operation result indicates success with partial processing
        assert result.result == "success"
        assert "Processed 3 resources" in result.messages  # Total resources considered
        assert "Loaded 1 resources" in result.messages  # Only 1 actually loaded
