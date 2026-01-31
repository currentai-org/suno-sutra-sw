The rootfs is built upon nvidia jetpack v6.2.1, installed to a device using nvidia sdk-manager.
Sdk-manager should have flashed the device pre-configured with username "ubuntu" and password "ubuntu".
Once the device comes online after flashing and enumerates as an RNDIS network interface, dependencies for this project can be installed using Ansible. First ensure the `ansible-core` package is installed. Then execute `ansible-playbook -i inventory ./install_all_usb.yml` to provision the device.
