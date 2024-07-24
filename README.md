# Documentation NVflare

## Important notices
This documentation uses nvflare version 2.4.1.


## New nvflare setup
This section details how to setup a new nvflare environment. The result is a working local environment with multiple clients, users and possibly servers.

### Preliminaries
You will need a python environment with NVflare installed.
You may use venv, conda (or even docker) to get a working nvflare environment.

Also, docker and docker compose should be installed on the host machine you are working on.

### Provisioning
Provisioning is the stage in which the certificates are generated. 
The following command creates a yaml file used to configure the participants under provision.yml. One can choose between HA and non-HA mode. If using HA, an overseer is created and multiple servers may be used as fallback. This is not strictly necessary if few participants and users are needed.
```shell
nvflare provision
```

Now, one may update the provision.yml file created.
This documentation assumes that the docker compose builder is used. The usage can be seen in the included example provision.yml file.

This provision file does not use an overseer and uses two clients. The base image in this case for the clients and servers is `projectmonai/monai` and a requirements file is provided.

If one now uses 
```bash
nvflare provision
```
a workspace is created in `workspace/<NAME>/prod_XX/`

The docker image to use is called `nvflare-service` by default. It is possible, however, to rename it in `.env` or to build the image every startup by changing the tag from `image` to `build`.
It is possible to start the processes in the created folder using `docker compose up`.
You may need to update the `.env` file if e.g. the python executable is not found in the given image.

### Accessing the console
#### Local access
One of the more elegant ways to access the nvflare environment running in docker compose locally is to start a container in the isolated network created by docker compose.

The first step to doing so is creating a custom name for the network. Edit the `.env` file and append 
```
COMPOSE_PROJECT_NAME=<NAME>
```
The network used by docker compose is called `<NAME>_default`.

You can now use the following script, here called `admin.sh`.
DO NOT USE THIS IF THE `.env` FILE IS NOT YOURS AND NOT STRICTLY AN ENVIRONMENT FILE.
Also, you will need to edit the user name. In this case, `admin@uksh.de` is used.
```bash
# DO NOT DO THIS WITH NON-ENV FORMAT FILES
source .env
docker run -it --rm --net=${COMPOSE_PROJECT_NAME}_default --volume ./admin@uksh.de:${WORKSPACE} $IMAGE_NAME ${WORKSPACE}/startup/fl_admin.sh
```

Enable the execution of `admin.sh` by using 
```bash
chmod +x ./bash.sh
```

Then, start the console by using 
```bash
./bash.sh
```


#### Remote access
Remotely, as is locally, accessing the console requires the workspace directory for the user. Transfer these files securely to your machine. Notice that security is breached if these files are transferred via a non-secure (ie. properly encrypted or better even, not using the internet) channel.

For remotely accessing the environment, host files need mapping. An example, akin to `admin.sh` is `admin-remote.sh`:
```bash
source .env
docker run -it --rm --net host --volume ./admin@uksh.de:${WORKSPACE} --add-host server1:$1 $IMAGE_NAME ${WORKSPACE}/startup/fl_admin.sh
```
One would start this script using 
```bash
./bash.sh 127.0.0.1
```

Notice that `--net host` is only necessary for local testing of this script and not strictly needed for remote access. It is not included in the provided `admin-remote.sh` file. 

Also, this script only assumes that one server is used and no overseer has been selected. Otherwise, the names need to be mapped as well.

## Non-Root mode
Best practice is to run the docker containers as non-root users. The dockerfile used in this repository uses root mode, but there is a non-root Dockerfile available as . 
Build this Dockerfile according to its comments.

The docker compose volume specified in compose.yaml for the server does not work with non-root access. Either remove its bound in the compose.yaml file or use a local directory with the needed permissions (i.e. read, write for the local user).


## Running an example project
This repository ships with an example project that trains a DenseNet121 model on the MedNIST dataset. 
The example project can be used for both local training and federated learning.