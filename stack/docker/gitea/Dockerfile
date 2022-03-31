FROM gitea/gitea:1.16

RUN apk --no-cache add sudo

COPY start_with_user.sh .
RUN chmod +x ./start_with_user.sh

ENTRYPOINT [ "./start_with_user.sh" ]
