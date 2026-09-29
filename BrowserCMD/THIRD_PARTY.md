# Third-Party Components

## Runtime

M1 uses `websockets` (`>=13,<16`) for the asynchronous Chrome DevTools Protocol connection. It is distributed under the BSD 3-Clause license. No browser binary is bundled.

## Development

- pytest (`>=8,<10`) is an optional test dependency, distributed under the MIT license.
- setuptools (`>=68,<81`) is the Python package build backend, distributed under the MIT license.

No vendored image decoder is present. Any later vendoring must record its exact source and license here before it is used.