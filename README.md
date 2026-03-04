# Suno Sutra Software

This repository contains all of the software required to prepare and operate a Suno Sutra pocket inference device. At it's core, Suno Sutra is an embedded linux device with application code running in Python. The python module can be used to describe applications that communicate with the UI (screen, buttons, microphone, speaker) and run AI inference on an array of supported models.

Contained within are:
* Scripts for creating and updating the [Root File System (rootfs)](./rootfs/)
    * These scripts can also be used to install models and other dependencies
* [Python classes](./python/) that enable communication with hardware
* [Python templates](./python/pocketinfer/applications/) for defining applications to run on device
* A [Python service](./python/pocketinfer/service.py) that can serve applications on the device

Since this is an embedded linux project, users can also simply shell into the device and install whatever software they like. However the application framework aims to simplify and streamline development. Break free from it if you like!

## Development Quickstart

This section implies you have access to a Suno Sutra prototype device and have connected to it over a USB-C cable. The device should enumerate as a USB RNDIS (Ethernet) network device, as well as a USB CDC device for fallback terminal access.

The easiest way to get up and running is to SSH into the device by executing `ssh ubuntu@192.168.55.1` with password `ubuntu`. Then the software can be edited directly on the device's filesystem. You could consider using VSCode with the Remote - SSH extension. For simplicity here's a sample way to get started that's fully terminal-based:

* Open a terminal and execute `ssh ubuntu@192.168.55.1` with password `ubuntu`
* Execute `cd ~/pocket-infer-sw/python/ && ls` to navigate to the python module you'll want to be editing
* Create a new application from the template by executing `cp applications/hear_the_world_en.py applications/<new name>.py`
* Edit the file with `vim applications/<new name>.py`. Rename the class from `HearTheWorldEn` to the name of your new application
* Edit the application manifest (which follows after `@RegisterApplication`). Update the name/description fields accordingly, and select any models and service_dependencies required by the application
* Implement your desired application in the `run(self)` method of the Application class - see comments for examples and tips
* Execute `sudo systemctl restart pocketinfer && journalctl -f -u pocketinfer` to restart the system service and view live logs. Use the device UI to activate the new application, and then watch the terminal 

## Hardware / Software Support

Platform:
* NVIDIA Jetson / Jetpack 6.2: Fully Supported
    * Other Jetpack versions: Untested
* Raspberry Pi 5: Not Supported yet
* Generic Linux: Not Supported Yet

Module:
* NVIDIA Jetson Orin Nano 8GB: Fully Supported
* NVIDIA Jetson Orin NX 8GB: In progress
* NVIDIA Jetson Orin NX 16GB: In progress
* NVIDIA jetson Thor: Not Supported Yet
* Raspberry Pi CM5: Not Supported Yet
* Hailo-10L: Not Supported Yet

Motherboard / Carrier Board / Development Board:
* NVIDIA Orin Nano 8GB Super Development Kit: Fully Supported
* Seeeedstudio ReComputer Mini Carrier Board: Fully Supported
* Waveshare NVIDIA Orin NX 16GB Development Kit: In Progress

# Software Components / Navigation

* For information about how to prepare a Root Filesystem image, to install dependencies or update dependencies, see the [rootfs](./rootfs/) subfolder.
* For information about the python library, which includes the Hardware Abstraction Layer (HAL), application templates and registry, model wrappers, application code and service, see the [python](./python/) subfolder.
* For firmware relating to the IO Expander component, see the [ioexpander](./ioexpander/) subfolder.

# Contribution / Development Tips

### Platform

To add support for a new platform, you will need to first define a base system image to start from. For the Jetson, this is the image provided by JetPack. Then starting from this base image, the Ansible roles in the [rootfs/roles](./rootfs/roles/) folder will need to be updated / specified.

Then it will be likely that a new board object will need to be created to capture any differences in the new platform. The new board object should be a subclass of the base Board object. Also be sure to update the `Board.get_board()` classmethod with code to auto-detect the new board.

### Model

To add support for a new model, first add an ansible role that will pull down any necessary system dependencies. If the new model requires a different set of python dependencies from [this module's requirements](./python/requirements.txt), then it's recommended to install and run the model from it's own virtual environment and create a simple API service.

Next write a new model python class, subclassed on the base model class. Define a `verify()` classsmethod that can check that the model is available and reayd for use. Define an `update()` classmethod that can be used to download any models or updates to the model. The `args` argument to these methods is a dictionary containing whatever values are specified in the application manifest decorator. So it may be helpful to also spin up a test application.