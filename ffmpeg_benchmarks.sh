#!/bin/bash
vod_url=$1
bitrates="64k 128k 256k 320k"
for vod in $vod_url; do
	echo $vod :
	m3u8_url=$(streamlink "$vod" audio --stream-url)
	duration=$(curl "$m3u8_url" -s | grep EXT-X-TWITCH-TOTAL-SECS | cut -d: -f 2 | cut -d. -f 1)
	echo duration $(date -d@"$duration" -u +%H:%M:%S)
	echo choose a transcoding setting that takes less than the duration of the vod
	for bitrate in $bitrates; do
		echo "benchmarking VBR aac to $bitrate CBR mp3"
		time (ffmpeg "-i" "$m3u8_url" "-c:a" "libmp3lame" "-ab" "$bitrate" "-f" "mp3" -hide_banner -loglevel error pipe:stdout > /dev/null)
		echo "benchmarking VBR aac to $bitrate CBR aac"
		time (ffmpeg "-i" "$m3u8_url" "-c:a" "aac" "-ab" "$bitrate" "-f" "adts" -hide_banner -loglevel error pipe:stdout > /dev/null)
	done
done
