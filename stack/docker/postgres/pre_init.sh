useradd -M postgres || true >> /dev/null
groupadd -f postgres >> /dev/null 
usermod -a -G postgres postgres >> /dev/null
docker volume create \
	--driver local \
	--opt o=addr=${HOMEPOSE_IP_ADDRESS},rw \
	--opt type=tmpfs \
	--opt device=:${POSTGRES_MOUNT_POINT} \
	postgresdata >> /dev/null
echo "HOST_POSTGRES_UID=$(id -u postgres)" > "${POSTGRES_COMPOSE_FILES_FOLDER}/.env"
echo "HOST_POSTGRES_GID=$(id -g postgres)" >> "${POSTGRES_COMPOSE_FILES_FOLDER}/.env"
