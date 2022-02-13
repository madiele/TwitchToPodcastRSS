#!/bin/bash
vod_url=$1
for vod in $vod_url; do
	echo $vod :
	m3u8_url=$(streamlink "$vod" audio --stream-url)
	bitrate=128k
	echo "benchmarking VBR aac to $bitrate CBR mp3"
	time (ffmpeg "-i" "$m3u8_url" "-c:a" "libmp3lame" "-ab" "$bitrate" "-f" "mp3" -hide_banner -loglevel error pipe:stdout > /dev/null)
	echo "benchmarking VBR aac to 128 kCBR aac"
	time (ffmpeg "-i" "$m3u8_url" "-c:a" "aac" "-ab" "$bitrate" "-f" "adts" -hide_banner -loglevel error pipe:stdout > /dev/null)
	bitrate=64k
	echo "benchmarking VBR aac to $bitrate CBR mp3"
	time (ffmpeg "-i" "$m3u8_url" "-c:a" "libmp3lame" "-ab" "$bitrate" "-f" "mp3" -hide_banner -loglevel error pipe:stdout > /dev/null)
	echo "benchmarking VBR aac to 128 kCBR aac"
	time (ffmpeg "-i" "$m3u8_url" "-c:a" "aac" "-ab" "$bitrate" "-f" "adts" -hide_banner -loglevel error pipe:stdout > /dev/null)
done
