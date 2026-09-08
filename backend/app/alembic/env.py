import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
assert config.config_file_name is not None
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# target_metadata = None

from geoalchemy2 import alembic_helpers  # noqa

from app.models import SQLModel  # noqa
from app.core.config import settings # noqa

target_metadata = SQLModel.metadata


# The postgis image installs postgis_tiger_geocoder + topology, whose tables all
# our migrations must ignore. The connect_args below pin reflection to `public`;
# this name filter is a backstop (the tiger geocoder tables come with `schema=None`
# once `tiger` is on the search_path, so filtering by schema alone isn't enough).
_EXTENSION_SCHEMAS = {"tiger", "tiger_data", "topology"}
_TIGER_NAMES = {
    "geocode_settings", "geocode_settings_default", "loader_platform",
    "loader_variables", "loader_lookuptables", "pagc_gaz", "pagc_lex",
    "pagc_rules", "topology", "layer", "addr", "addrfeat", "bg", "county",
    "county_lookup", "countysub_lookup", "cousub", "direction_lookup", "edges",
    "faces", "featnames", "place", "place_lookup", "secondary_unit_lookup",
    "state", "state_lookup", "street_type_lookup", "tabblock", "tabblock20",
    "tract", "zcta5", "zip_lookup", "zip_lookup_all", "zip_lookup_base",
    "zip_state", "zip_state_loc",
}


def _include_object(obj, name, type_, reflected, compare_to):
    schema = getattr(obj, "schema", None) or getattr(
        getattr(obj, "table", None), "schema", None
    )
    if schema in _EXTENSION_SCHEMAS:
        return False
    if name and (name in _TIGER_NAMES or name.startswith("idx_tiger")):
        return False
    # PostGIS-managed objects in public (spatial_ref_sys, spatial indexes,
    # geometry_columns, ...) so autogenerate / `alembic check` stay clean.
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    return str(settings.DATABASE_URL)


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=_include_object,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    assert configuration is not None
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Pin every connection's search_path to `public` at connect time (libpq
        # option, no transaction) so reflection ignores the tiger/topology
        # schemas the PostGIS image adds to the DB search_path.
        connect_args={"options": "-csearch_path=public"},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=_include_object,
            render_item=alembic_helpers.render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
