#!/usr/bin/env bash
set -e
cd "${BASH_SOURCE%/*}/" || exit

cd ..
rm -rf geojson
mkdir geojson

yarn

yarn shp2json data/shp/countries/*.shp -o data/geojson/countries.geojson --encoding utf8
yarn shp2json data/shp/units/*.shp -o data/geojson/units.geojson --encoding utf8
yarn shp2json data/shp/subunits/*.shp -o data/geojson/subunits.geojson --encoding utf8
yarn shp2json data/shp/states/*.shp -o data/geojson/states.geojson --encoding utf8

rm -r data/shp