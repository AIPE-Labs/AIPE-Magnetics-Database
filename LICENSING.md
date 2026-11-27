# Licensing and data rights

Three things are licensed separately.

**Code** (the Python package, importers, tools, schemas, plugins, the Data Explorer and tests) is released under the
[MIT licence](LICENSE).

**Third-party data** keep the licence of their source; every record carries it in `license` and in each evidence
item. Nothing is relicensed, and the MIT licence of the code does not extend to these files.

**AIPE's own data layer** (the selection and arrangement of the records, the normalisation to schema v0.2, the canonical
catalogue in `data/canonical`, quality flags and reports, and the documentation) is offered under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) to the extent that AIPE holds rights in it. This adds no
restriction to the upstream data and cannot grant rights that the upstream owners did not give. Attribution: "AIPE
Magnetics Database, Fulong Li and contributors", with the repository URL and the version or commit used.

The `pyproject.toml` licence expression (`MIT AND Apache-2.0 AND CC-BY-4.0 AND GPL-3.0-only`) describes the wheel as a
whole, because the wheel bundles the committed data; the code in it is MIT.

The names "AIPE", "AIPE Labs" and "AI for Power Engineering" and their logos are not covered by these licences. Forks
and redistributions are welcome under the terms above, but must not suggest that they are the AIPE project or are
endorsed by it.

| Data | Licence | Notes |
| --- | --- | --- |
| `data/normalized/mas`, `data/raw/mas` (OpenMagnetics MAS, commit `c33ccfec`) | Apache-2.0 | upstream licence in `data/raw/mas/LICENSE.upstream.md`; most values originate from manufacturer datasheets, whose terms the MAS licence does not cover |
| `data/normalized/princeton-magnet` (PrincetonUniversity/magnet `8a6892e9`) | MIT | cite the three MagNet IEEE TPEL papers (dataset record) |
| `data/normalized/princeton-magnet-scope` (MagNet raw oscilloscope captures of N87, same repository) | MIT | cite the MagNet IEEE TPEL papers; the waveform files are on Hugging Face only |
| `data/normalized/paderborn-lea`, `data/raw/paderborn-lea` (upb-lea/materialdatabase `04fff8e9`) | GPL-3.0-only | separate copyleft subtree with LICENSE and NOTICE (modification statement, source offer) |
| `data/normalized/hefmag`, `data/raw/hefmag` (Zenodo 8292861) | CC-BY-4.0 | attribution: Ragusa, Dobak, Beatrice, Fiorillo (EMPIR 19ENG06 HEFMAG) |
| `data/normalized/zenodo-smc-ferrite-triangular`, `data/raw/...` (Zenodo 21626116) | CC-BY-4.0 | attribution: Dobak, Onderko, Fuzer, Kollar |
| `data/normalized/nabih-magneto`, `data/raw/nabih-magneto` (asalahnabih/magneto `0a3a0f1e`) | MIT | cite per the upstream CITATION.cff (A. Nabih, Virginia Tech); `derived/` is a TSV export, not an original |
| `data/normalized/guillod-n87-dielectric`, `data/raw/guillod-n87-dielectric` (otvam/large_signal_ferrite_apec24 `dd068898`) | MIT | Guillod, Roberts, Sullivan, APEC 2024; the repository's datasheet- and MagNet-derived permeability folders are not included |
| `data/normalized/zenodo-7368936-cwh-n87` (Zenodo 7368936; raw on Hugging Face) | CC-BY-4.0 | attribution: Guillod, Lee, Li, Wang, Chen, Sullivan; measurements from MagNet |
| `data/normalized/zenodo-10725890-inrim`, `data/raw/zenodo-10725890-inrim` (Zenodo 10725890) | CC-BY-4.0 | attribution: M. Pasquale, INRIM |
| curated catalogue in `src/aipe_magnetics_database/data/catalog` | NOASSERTION | individual datasheet values transcribed with locators; documents referenced, not copied |
| PSMA core-loss studies, ASU MHz aggregate, MagNet Challenge 1/2, DTU IEEE DataPort set, unlicensed GitHub data, manufacturer tools | not redistributed | reference entries and user-supplied-file adapters only ([docs/source-catalogue.md](docs/source-catalogue.md)) |

Third-party code dependencies (numpy BSD-3-Clause; pydantic, jsonschema, referencing, mcp MIT; h5py BSD-3-Clause) keep
their licences. Public availability is not redistribution permission; rights holders may request removal of values
through an issue.

The Hugging Face dataset [AIPE-Labs/AIPE-Magnetics-Dataset](https://huggingface.co/datasets/AIPE-Labs/AIPE-Magnetics-Dataset)
republishes only the sources above whose licence permits redistribution (not the NOASSERTION curated catalogue); each
`raw/<source-id>/` and `normalized/v0.2/<source-id>/` subtree and each `tabular/v0.2/<config>/<source-id>.parquet` file
keeps its source licence (`LICENSE.md` there).
