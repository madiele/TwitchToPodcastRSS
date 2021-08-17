# this is ste script to generate new copiled images for every architecture on windows and then push to docker.hub
docker.exe buildx build --push --platform "linux/arm/v7,linux/arm64/v8,linux/amd64,linux/386" --tag "madiele/twitch_to_podcast_rss:latest" --tag "madiele/twitch_to_podcast_rss:<VERSION> .
