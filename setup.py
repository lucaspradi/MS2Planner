import setuptools

setuptools.setup(
    name="ms2planner",
    version="0.0.1",
    author="Lucas Pradi",
    author_email="author@example.com",
    description="A small example package",
    long_description="A small example package",
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'ms2planner=ms2planner.path_finder:main',
        ],
    },
) 