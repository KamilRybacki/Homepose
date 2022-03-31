chown -R www-data:www-data ${NEXTCLOUD_MOUNT_POINT}
chown -R www-data:www-data ${NEXTCLOUD_DATA_MOUNT_POINT}
rm -r ${COMPOSE_FILES_FOLDER}/nextcloud/nextcloud-deploy-entrypoint
