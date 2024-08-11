# FAQ NVflare


## Which Firewall-settings must be set?
1. Clients do not have incoming connections, only outgoing ones
2. Servers need to open two ports:
	1. Port for communication with clients
	2. Port for communication with admin consoles
3. Overseers need to open a single port

All clients must have outgoing access to servers and overseers, servers and overseers must be able to accept all incoming connections from the clients.

## Is it possible to add participants dynamically?
Once an nvflare setup is complete, it is possible to add new clients and admin consoles dynamically. It is not, however, possible to add new servrs and overseers.

See https://nvflare.readthedocs.io/en/main/user_guide/nvflare_cli/provision_command.html#dynamic-provisioning for more.

## Which hardware is required?
Apart from networking settings described above, typical deep-learning hardware may be employed for usage in NVflare.
You will need: one or multiple graphics cards best if somewhat up to date. On of the best options around at this time is the NVIDIA H100/H200. Consumer grade cards may also work, however and are significantly cheaper.
In addition, a somewhat new CPU and RAM needed to train a deep learning network traditionally will suffice.
