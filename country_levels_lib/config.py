import pathlib

lib_dir = pathlib.Path(__file__).parent.resolve()
root_dir = lib_dir.parent

data_dir = root_dir / 'data'
geojson_dir = data_dir / 'geojson'
wikidata_dir = data_dir / 'wikidata'
tmp_dir = data_dir / 'tmp'

export_dir = root_dir.parent / 'country-levels-export'
export_geojson_dir = export_dir / 'geojson'
docs_dir = export_dir / 'docs'

fixes_dir = root_dir / 'fixes'
