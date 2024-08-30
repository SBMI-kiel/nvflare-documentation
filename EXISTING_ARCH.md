# Attaching to an existing NVflare architecture

## Requirements
You will need:
1. Docker compatibility 
3. Network access to the hosting site's opened ports (ie two per server, one per overseer)
4. Encryption certs from the host (transferred via a secure path)


## Initial connection
In order to connect to the servers, you will need to start up a docker client (of course, running on metal is possible but isolation is often beneficial and easier).

If the following steps are executed correctly and the servers are running, you will be greeted by a successful connection log in the console.

This docker compose service serves as an example to running a client. You may port this setup to a non-compose equivalent.

```yaml
  site-1:
    command:
    - ${PYTHON_EXECUTABLE}
    - -u
    - -m
    - nvflare.private.fed.app.client.client_train
    - -m
    - /workspace/
    - -s
    - fed_client.json
    - --set
    - secure_train=true
    - uid=site-1
    - org=uksh
    - config_folder=config
    container_name: site-1
    image: ${IMAGE_NAME}
    volumes:
    - ./site-1:/workspace/
```
### Entrypoint
The entrypoint may be parsed from the yaml above.

### Volumes
You will need to map the cert folder supplied by the NVflare-architecture admins to be in the docker container.
The default path in the container is `/workspace/`.



### Hostnames
Often, no public DNS entries have been created for the servers. If this is the case, hostname entries need to be made for the docker container.
To do so, use:
for docker compose:
```yaml
extra_hosts:
  - "server:0.0.0.0"
```

If using a normal docker container however, the syntax in the start command becomes:
```commandline
docker run ... --add-host server:0.0.0.0
```

where 0.0.0.0 is the given IP address. Notice that the ip addresses of all servers need mapping and naturally, the names need to match with those in the NVflare architecture.
Ask the administrators for the needed names if unknown.

## Running a federated project
This assumes that code adapted to NVflare has been provided and the data has been processed and is accessible. It also assumes the previous initial connection was successful.

The only change that needs to be made for the docker container is that the data and the code is mounted and the code is in the python path environment variable, called `PYTHONPATH`. This means that the code can be seen by python.

Otherwise, starting the container up like before will suffice.

