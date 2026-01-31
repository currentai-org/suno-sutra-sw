from setuptools import setup, find_packages

setup(
    name='pocketinfer',
    version='0.1.0',
    packages=find_packages(),
    # Additional metadata
    author='Andrew Tergis',
    author_email='theterg@gmail.com',
    description='Python code supporting the pocket-infer device',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    license='MIT',
    install_requires=[
        'pyserial',
        'ollama',
        'pyaudio',
        'numpy',
        'SpeechRecognition',
        'vosk',
        'piper-tts',
        'appdirs',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)