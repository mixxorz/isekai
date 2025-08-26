# ISEKAI

**ISEKAI** is a general-purpose ETL framework for Django. It helps you migrate any data (including files) from any source into your Django models using a clear, pluggable pipeline. ISEKAI makes it simple to bring data from anywhere into Django models.

## Why ISEKAI?

Django projects often need to bring data from a wide variety of sources into structured models, but writing ad-hoc scripts for this quickly becomes messy and repetitive. ISEKAI offers a clear, reusable framework for defining ETL pipelines so your migrations stay predictable, testable, and easy to maintain.

## Concepts

At the core of ISEKAI is the **Resource** model. A Resource represents a single distinct piece of data you want to migrate. As it moves through the pipeline, the Resource accumulates data and undergoes transformations, and by the final stage it resolves to a single Django model instance. In other words, every Resource eventually becomes one record in your database, and the pipeline describes how it gets there.

The pipeline has five stages:

1. **Seed** - Create the initial set of Resources, often by reading from a sitemap, CSV file, database table, or another source through custom seeders.
2. **Extract** - Using those keys, fetch the raw bytes from the source, whether that's through the web with the HTTPExtractor or any other system via a custom extractor.
3. **Mine** - Inspect extracted data to discover or 'mine" related Resources. For example, the HTMLImageMiner will create new Resources for each image it finds linked in an HTML page.
4. **Transform** - Using the data on the Resource, produce a target Spec (your project's model-shaped representation) that the Load stage will create in Django.
5. **Load** - Create the Django models from the Resource's Spec. This stage calculates the optimal build order for the objects, and can reconcile circular dependencies through a two-phase create mechanism.

Each stage is handled by **processors**. ISEKAI includes built-in processors for common use cases, but you can also write your own. This means you can extract resources from any source, apply custom transformations, and load into any Django model structure.

## License

MIT
