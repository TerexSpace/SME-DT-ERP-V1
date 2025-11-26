#!/usr/bin/env python3
"""
Setup script for SME-DT-ERP package.

Installation:
    pip install -e .

For development:
    pip install -e ".[dev]"
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
requirements = [
    "simpy>=4.1.0",
    "numpy>=1.21.0",
]

dev_requirements = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "sphinx>=7.0.0",
    "sphinx-rtd-theme>=2.0.0",
]

setup(
    name="sme-dt-erp",
    version="0.1.0",
    author="Almas Ospanov",
    author_email="a.ospanov@astanait.edu.kz",
    description="Digital Twin Framework for ERP-Integrated Warehouse Management in SMEs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TerexSpace/SME-DT-ERP-V1",
    project_urls={
        "Bug Tracker": "https://github.com/TerexSpace/SME-DT-ERP-V1/issues",
        "Documentation": "https://github.com/TerexSpace/SME-DT-ERP-V1",
        "Source Code": "https://github.com/TerexSpace/SME-DT-ERP-V1",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords=[
        "digital-twin",
        "erp",
        "warehouse-management",
        "sme",
        "simulation",
        "discrete-event-simulation",
        "industry-4.0",
        "supply-chain",
    ],
    packages=find_packages(exclude=["tests", "tests.*", "docs", "examples"]),
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
        "test": ["pytest>=7.0.0", "pytest-cov>=4.0.0"],
        "docs": ["sphinx>=7.0.0", "sphinx-rtd-theme>=2.0.0"],
    },
    entry_points={
        "console_scripts": [
            "sme-dt-erp=sme_dt_erp.core:main",
            "sme-dt-erp-sim=sme_dt_erp.run_simulation:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
