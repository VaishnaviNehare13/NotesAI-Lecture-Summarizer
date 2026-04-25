from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript("jNQXAC9IVRw")
print(transcript[:2])
