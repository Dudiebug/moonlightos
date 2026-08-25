# Source code for distributed software

MoonlightOS provides source and license information for the exact software in
each ISO under `/usr/share/doc/moonlightos/`. The release's GitHub-generated
source archive contains the MoonlightOS build scripts and configuration.

The ISO also contains the pinned upstream source snapshots and complete license
texts for Moonlight Qt 6.1.0 and chiaki-ng 1.10.0 under
`/usr/share/doc/moonlightos/source/` and `/usr/share/doc/moonlightos/licenses/`.
Their original repositories, including submodule revision records and history,
are:

- https://github.com/moonlight-stream/moonlight-qt/tree/v6.1.0
- https://github.com/streetpea/chiaki-ng/tree/v1.10.0

`debian-packages.tsv` records every installed Debian binary package, its exact
version, source package, and source version. Debian source packages can be
obtained from https://sources.debian.org/ and https://snapshot.debian.org/.
Package-specific license notices remain in `/usr/share/doc/*/copyright`.

Optional browsers are not part of the ISO. The device owner may ask the
Settings screen to install Firefox ESR or Chromium directly from Debian's
signed repositories after installation.

If a listed source cannot be obtained from those locations, open a source-code
request at https://github.com/Dudiebug/moonlightos/issues. Provide the ISO
version, package name, and package version. MoonlightOS will provide the source
at no charge other than reasonable physical-media and shipping costs when
physical delivery is requested.
