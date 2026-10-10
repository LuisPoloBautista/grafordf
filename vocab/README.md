# Ontología de referencia

`bibframe.rdf` es la ontología oficial de Library of Congress, descargada de
https://raw.githubusercontent.com/lcnetdev/bibframe-ontology/master/bibframe.rdf
durante esta revisión. Declara `owl:versionInfo` 2.0.1 (familia BIBFRAME 2.0).

Se conserva la copia local para validación reproducible sin acceso de red.
`reports/rdf-validation.json` registra su SHA-256 y versión; si se actualiza
la copia deben revisarse las decisiones del perfil y repetirse las pruebas.

La tabla de idiomas de `bibliographic_normalization.py` utiliza los códigos
MARC bibliográficos documentados por LC, incluyendo fre/ger/dut/rum. Fuentes:
https://www.loc.gov/marc/languages/language_name.html y
https://www.loc.gov/standards/iso639-2/php/code_list2.php .
