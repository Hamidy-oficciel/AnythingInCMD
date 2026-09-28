from setuptools import Extension, setup


setup(
    ext_modules=[
        Extension(
            "youtubecmd._native_renderer",
            ["src/youtubecmd/_native_renderer.c"],
            optional=True,
        )
    ]
)