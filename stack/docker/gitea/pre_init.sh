GITEA_GENERATED_SECRET="${GITEA_COMPOSE_FILES_FOLDER}/.env"
if [ ! -f ${GITEA_GENERATED_SECRET} ]; then
    echo 'Secret ENVFILE not found. Exporting generated GITEA_SECRET.'
    echo "GITEA_SECRET=${GITEA_SECRET}" > "${GITEA_COMPOSE_FILES_FOLDER}/.env"
fi

echo 'Generating entrypoint script to create admin user'
echo '#!/usr/bin/env bash
ATTEMPT=0
MAX_ATTEMPT=20
while true; do
    sleep 1
    ATTEMPT=$(($ATTEMPT + 1))
    STATUS_CODE=$(curl -LI localhost:3000 -o /dev/null -w '%{http_code}\n' -s)
    if [ $STATUS_CODE = "200n" ]; then
        echo "Gitea is ready"
        echo "Create Gitea admin"
        sudo -u git gitea admin user create \
            --username '"${GITEA_ADMIN_USERNAME}"' \
            --password '"${GITEA_ADMIN_PASSWORD}"' \
            --email '"${NOTIFICATIONS_EMAIL}"' \
            --must-change-password=false \
            --admin
        exit 0
    elif [ $ATTEMPT = $MAX_ATTEMPT ]; then
        exit 1
    fi;
done & /usr/bin/entrypoint' > ${GITEA_COMPOSE_FILES_FOLDER}/start_with_user.sh
