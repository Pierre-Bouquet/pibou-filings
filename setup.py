from setuptools import setup, find_packages

setup(
    name="piboufilings",
    version="0.3.0",
    description="A Python library for downloading and parsing SEC EDGAR filings",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Pierre Bouquet",
    author_email="pierrebouquet73000@gmail.com",
    url="https://github.com/pibou/piboufilings",
    packages=find_packages(),
    install_requires=[
        "pandas>=1.3.0",
        "requests>=2.26.0",
        "tqdm>=4.62.0",
        "urllib3>=1.26.0",
        "lxml>=4.9.0",  # For XML parsing
        "python-dateutil>=2.8.2",  # For date parsing
    ],
    python_requires=">=3.8",  # Updated from >=3.7
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        # Remove Python 3.7
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    keywords="sec, edgar, filings, financial, 13f, parser",
    project_urls={
        "Bug Reports": "https://github.com/pibou/piboufilings/issues",
        "Source": "https://github.com/pibou/piboufilings",
    },
)
