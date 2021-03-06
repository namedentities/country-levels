import shutil
import sys

from country_levels_lib.fips import fips_utils
from country_levels_lib.config import export_dir, fixes_dir
from country_levels_lib.geo import calculate_centroid, find_timezone
from country_levels_lib.utils import read_json, osm_url, write_json, wikidata_url
from country_levels_lib.wam.wam_collect import validate_iso1, validate_iso2, simp_dir
from country_levels_lib.wam.wam_download import wam_data_dir
from area import area


population_map = None
population_fixes = read_json(fixes_dir / 'population.json')
timezone_fixes = read_json(fixes_dir / 'timezone.json')
us_states_by_postal = fips_utils.get_state_data()[1]
iso1_json = None
iso2_json = None


def split_geojson(iso_level: int, simp_level: str):
    global population_map, iso1_json, iso2_json
    if not population_map:
        population_map = read_json(wam_data_dir / 'population.json')

    if simp_level != 'high':
        iso1_json = read_json(export_dir / 'iso1.json')
        iso2_json = read_json(export_dir / 'iso2.json')

    print(f'Splitting iso{iso_level} to level: {simp_level}')
    file_path = simp_dir / simp_level / f'iso{iso_level}.geojson'

    features = read_json(file_path)['features']
    features_sorted = sorted(features, key=lambda i: i['properties']['admin_level'])

    features_by_iso = dict()

    for feature in features_sorted:
        feature_processed = process_feature_properties(feature, iso_level, simp_level)
        if feature_processed is None:
            continue
        feature_clean = feature_processed['feature']

        iso = feature_processed['iso']
        if iso_level == 1:
            if not validate_iso1(iso):
                print(f'invalid iso1: {iso}')
                continue
        else:
            if not validate_iso2(iso):
                print(f'invalid iso2: {iso}')
                continue

        features_by_iso.setdefault(iso, list())
        features_by_iso[iso].append(feature_clean)

    deduplicated_by_iso = deduplicate_features_by_iso(features_by_iso)
    write_json_and_geojsons(deduplicated_by_iso, iso_level, simp_level)


def process_feature_properties(feature: dict, iso_level: int, simp_level: str):
    prop = feature['properties']
    alltags = prop['alltags']

    name = prop.pop('name')
    osm_id = int(prop.pop('id'))
    iso = prop.pop(f'iso{iso_level}')
    countrylevel_id = f'iso{iso_level}:{iso}'

    if iso_level == 1:
        iso_json = iso1_json
    else:
        iso_json = iso2_json

    if simp_level == 'high':
        centroid = calculate_centroid(feature)
        center_lat = centroid['lat']
        center_lon = centroid['lon']
        area_m2 = int(area(feature['geometry']))
    else:
        center_lat = iso_json[iso]['center_lat']
        center_lon = iso_json[iso]['center_lon']
        area_m2 = iso_json[iso]['area_m2']

    if not feature['geometry']:
        print(f'  missing geometry: {countrylevel_id}')
        if simp_level == 'high':
            sys.exit('high level missing geometry')

        geojson_path = iso_json[iso]['geojson_path']
        feature['geometry'] = get_geometry_from_medium_high(geojson_path)

    admin_level = int(prop.pop('admin_level'))
    wikidata_id = prop.pop('wikidata_id', None)
    population = population_map.get(wikidata_id)
    if countrylevel_id in population_fixes:
        if population:
            print(f'Population not needed anymore in fixes: {countrylevel_id}')
        population = population_fixes[countrylevel_id]

    timezone = alltags.pop('timezone', None)
    if not timezone:
        timezone = find_timezone(center_lon, center_lat)
        if not timezone:
            timezone = timezone_fixes.get(countrylevel_id)
        if not timezone:
            print(f'missing timezone for {countrylevel_id} {name}')

    # override population for US states from Census data
    if iso.startswith('US-'):
        postal_code = iso[3:]
        state_data = us_states_by_postal.get(postal_code, {})
        population_from_census = state_data.get('population')
        if population_from_census is not None:
            population = population_from_census

    wikipedia_from_prop = prop.pop('wikipedia', None)
    wikipedia_from_alltags = alltags.pop('wikipedia', None)
    if (
        wikipedia_from_prop
        and wikipedia_from_alltags
        and wikipedia_from_prop != wikipedia_from_alltags
    ):
        print(wikipedia_from_prop, wikipedia_from_alltags)
    wikipedia_id = wikipedia_from_alltags
    if wikipedia_from_prop:
        wikipedia_id = wikipedia_from_prop

    feature.pop('bbox', None)

    for key in ['boundary', 'note', 'rpath', 'srid', 'timestamp']:
        prop.pop(key, None)

    for key in [
        'ISO3166-1',
        'ISO3166-1:alpha2',
        'ISO3166-1:numeric',
        'ISO3166-2',
        'ISO3166-2:alpha2',
        'ISO3166-2:numeric',
        'land_area',
        'wikidata',
    ]:
        alltags.pop(key, None)

    new_prop = {
        'name': name,
        f'iso{iso_level}': iso,
        'admin_level': admin_level,
        'osm_id': osm_id,
        'countrylevel_id': countrylevel_id,
        'osm_data': prop,
        'center_lat': round(center_lat, 2),
        'center_lon': round(center_lon, 2),
        'area_m2': area_m2,
    }

    if timezone:
        new_prop['timezone'] = timezone

    if population:
        new_prop['population'] = population

    if wikidata_id:
        new_prop['wikidata_id'] = wikidata_id

    if wikipedia_id:
        new_prop['wikipedia_id'] = wikipedia_id

    feature['properties'] = new_prop

    return {
        'feature': feature,
        'iso': iso,
    }


def deduplicate_features_by_iso(features_by_iso: dict):
    deduplicated = {}
    for iso, features in features_by_iso.items():
        if len(features) == 1:
            deduplicated[iso] = features[0]
        else:
            print(f'  duplicate features for: {iso}')
            for feature in features:
                prop = feature['properties']
                name = prop['name']
                admin_level = prop['admin_level']
                osm_id = prop['osm_id']
                population = prop.get('population')
                wikidata_id = prop.get('wikidata_id')

                print(
                    f'    {name} '
                    f'admin_level: {admin_level}  '
                    f'population: {population}  '
                    f'{osm_url(osm_id)} '
                    f'{wikidata_url(wikidata_id)}  '
                )

            # pick the first one by admin_level
            features_sorted = sorted(features, key=lambda k: k['properties']['admin_level'])
            deduplicated[iso] = features_sorted[0]
            print()
    return deduplicated


def write_json_and_geojsons(deduplicated_by_iso: dict, iso_level: int, simp_level: int):
    assert iso_level in [1, 2]

    level_subdir = export_dir / 'geojson' / simp_level / f'iso{iso_level}'
    shutil.rmtree(level_subdir, ignore_errors=True)
    level_subdir.mkdir(parents=True)

    json_data = {}
    for iso, feature in deduplicated_by_iso.items():
        new_prop_without_osm_data = {
            k: v for k, v in feature['properties'].items() if k != 'osm_data'
        }
        json_data[iso] = new_prop_without_osm_data

        if iso_level == 1:
            write_json(level_subdir / f'{iso}.geojson', feature)
            json_data[iso]['geojson_path'] = f'iso1/{iso}.geojson'

        else:
            iso2_start, iso2_end = iso.split('-')

            iso2_subdir = level_subdir / iso2_start
            iso2_subdir.mkdir(exist_ok=True)

            write_json(level_subdir / iso2_start / f'{iso}.geojson', feature)
            json_data[iso]['geojson_path'] = f'iso2/{iso2_start}/{iso}.geojson'

    if simp_level == 'high':
        write_json(export_dir / f'iso{iso_level}.json', json_data, indent=2, sort_keys=True)


def get_geometry_from_medium_high(geojson_path):
    medium_geojson_path = export_dir / 'geojson' / 'medium' / geojson_path
    high_geojson_path = export_dir / 'geojson' / 'high' / geojson_path

    if medium_geojson_path.is_file():
        medium_geojson = read_json(medium_geojson_path)
        if medium_geojson['geometry']:
            print('    using geometry from medium geojson')
            return medium_geojson['geometry']

    high_geojson = read_json(high_geojson_path)
    print('    using geometry from high geojson')
    return high_geojson['geometry']
