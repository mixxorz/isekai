from typing import overload

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from freezegun import freeze_time
from wagtail.images.models import Image

from isekai.loaders import ModelLoader
from isekai.operations.load import load
from isekai.types import BlobRef, FileRef, InMemoryFileRef, Key, Ref, Spec
from tests.testapp.models import Article, Author, AuthorProfile, ConcreteResource, Tag


@pytest.mark.django_db
class TestModelLoader:
    def test_load_spec_with_blob(self):
        @overload
        def resolver(ref: BlobRef) -> FileRef: ...
        @overload
        def resolver(ref: Ref) -> int | str: ...

        def resolver(ref: Ref) -> FileRef | int | str:
            with open("tests/files/blue_square.jpg", "rb") as f:
                return InMemoryFileRef(f.read())
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

        image = objects[0]
        assert isinstance(image, Image)
        assert image.title == "blue_square.jpg"
        assert image.description == "A sample image"

        with open("tests/files/blue_square.jpg", "rb") as f:
            expected_content = f.read()

        # Read from the saved file to compare content
        with image.file.open() as saved_file:
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
        author = objects[0]
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
                "author": Ref(author_key),
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article in results
        author = next(obj for obj in objects if isinstance(obj, Author))
        article = next(obj for obj in objects if isinstance(obj, Article))

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
                "author": Ref(author_key),
                "tags": [
                    Ref(tag1_key),
                    Ref(tag2_key),
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
        tags = [obj for obj in objects if isinstance(obj, Tag)]
        author = next(obj for obj in objects if isinstance(obj, Author))
        article = next(obj for obj in objects if isinstance(obj, Article))

        assert len(tags) == 2
        assert article.author == author

        # Check M2M relationships
        article_tags = list(article.tags.all())
        assert len(article_tags) == 2
        tag_names = {tag.name for tag in article_tags}
        assert tag_names == {"Python", "Django"}

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
                    "mentor": Ref(mentor_key),
                },
            },
        )

        objects = loader.load(
            [(mentor_key, mentor_spec), (author_key, author_spec)], resolver
        )

        assert len(objects) == 2

        # Find objects
        mentor = next(
            obj for obj in objects if getattr(obj, "name", None) == "Carol Mentor"
        )
        author = next(
            obj for obj in objects if getattr(obj, "name", None) == "Bob Writer"
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
                "author": Ref(Key(type="author", value="existing_author")),
            },
        )

        objects = loader.load([(article_key, article_spec)], resolver)

        assert len(objects) == 1
        article = objects[0]
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
                    "featured_article": Ref(
                        article_key
                    ),  # Author references article in JSON
                },
            },
        )

        article_spec = Spec(
            content_type="testapp.Article",
            attributes={
                "title": "Circular Article",
                "content": "This article references its author.",
                "author": Ref(author_key),  # Article references author via FK
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj for obj in objects if isinstance(obj, Author))
        article = next(obj for obj in objects if isinstance(obj, Article))

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
                    "mentor": Ref(mentor_key),  # Self-reference via JSON field
                },
            },
        )

        objects = loader.load(
            [(mentor_key, mentor_spec), (student_key, student_spec)], resolver
        )

        assert len(objects) == 2
        mentor = next(
            obj for obj in objects if getattr(obj, "name", None) == "Mentor Author"
        )
        student = next(
            obj for obj in objects if getattr(obj, "name", None) == "Student Author"
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
                "author": Ref(author_key),
                "tags": [
                    Ref(new_tag_key),  # Internal reference to new tag
                    Ref(
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
        article = next(obj for obj in objects if isinstance(obj, Article))

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
                "author": Ref(author_key),
                # Note: Empty M2M list [] would be handled by M2M phase, not included here
                "metadata": None,  # Explicit null value
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj for obj in objects if isinstance(obj, Author))
        article = next(obj for obj in objects if isinstance(obj, Article))

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
                "author": Ref(author_key),  # OneToOne reference
                "website": "https://example.com",
                "twitter_handle": "@profile_author",
                "settings": {"theme": "dark", "notifications": True},
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj for obj in objects if isinstance(obj, Author))
        profile = next(obj for obj in objects if isinstance(obj, AuthorProfile))

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
                "author": Ref(Key(type="author", value="existing_oto_author")),
                "website": "https://external.example.com",
                "settings": {"external": True},
            },
        )

        objects = loader.load([(profile_key, profile_spec)], resolver)

        assert len(objects) == 1
        profile = objects[0]
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
                "author": Ref(author1_key),
                "website": "https://jsontest.example.com",
                "settings": {
                    "preferred_collaborator": Ref(author2_key),  # Ref in JSON
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
            obj for obj in objects if getattr(obj, "name", None) == "JSON Author 1"
        )
        author2 = next(
            obj for obj in objects if getattr(obj, "name", None) == "JSON Author 2"
        )
        profile = next(obj for obj in objects if isinstance(obj, AuthorProfile))

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
                "author_id": Ref(author_key),  # Using _id suffix
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (article_key, article_spec)], resolver
        )

        assert len(objects) == 2

        # Find author and article in results
        author = next(obj for obj in objects if isinstance(obj, Author))
        article = next(obj for obj in objects if isinstance(obj, Article))

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
                "author_id": Ref(author_key),  # Using _id suffix for OneToOne
                "website": "https://otoid.example.com",
                "settings": {"test": True},
            },
        )

        objects = loader.load(
            [(author_key, author_spec), (profile_key, profile_spec)], resolver
        )

        assert len(objects) == 2
        author = next(obj for obj in objects if isinstance(obj, Author))
        profile = next(obj for obj in objects if isinstance(obj, AuthorProfile))

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


@pytest.mark.django_db
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
            load()

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
                "author": str(Ref(Key.from_string(author_resource.key))),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )
        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            load()

        author = Author.objects.get()
        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.bio == {"expertise": "Django", "years_experience": 5}

        article = Article.objects.get()
        assert article.title == "Test Article"
        assert article.content == "This is a test article."
        assert article.author == author

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
                "bio": {"featured_articles": [str(Ref(article_key))]},
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
                "author": str(Ref(Key.from_string(author_resource.key))),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        author_resource.dependencies.add(article_resource)
        article_resource.dependencies.add(author_resource)

        now = timezone.now()
        with freeze_time(now):
            load()

        author = Author.objects.get()
        article = Article.objects.get()

        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
        assert author.bio == {"featured_articles": [article.pk]}

        assert article.title == "Test Article"
        assert article.content == "This is a test article."
        assert article.author == author

    def test_load_object_depends_on_existing_object(self):
        raise AssertionError("This test is not implemented yet.")
