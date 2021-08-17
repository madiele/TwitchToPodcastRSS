# this is ste script to generate new copiled images for every architecture on windows and then push to docker.hub
param($version)
if ($version -eq $null) {
	$version = read-host -Prompt "pleas input version to push example: v1.2"
}
docker.exe buildx build --push --platform "linux/arm/v7,linux/arm64/v8,linux/amd64,linux/386" --tag "madiele/twitch_to_podcast_rss:$version" --tag "madiele/twitch_to_podcast_rss:latest" .
