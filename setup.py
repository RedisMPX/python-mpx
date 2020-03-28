import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="redismpx", # Replace with your own username
    version="0.1.0",
    author="Loris Cro",
    author_email="kappaloris@gmail.com",
    description="A Redis Pub/Sub multiplexer.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/RedisMPX/python-mpx",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=['aioredis'],
    python_requires='>=3.6',
)