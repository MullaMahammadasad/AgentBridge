from setuptools import setup, find_packages

setup(
    name="json_browser",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "playwright>=1.40.0",
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.5.0",
        "websockets>=12.0",
        "beautifulsoup4>=4.12.2",
    ],
)
