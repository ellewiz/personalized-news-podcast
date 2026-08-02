from podcast import pipeline

if __name__ == "__main__":
    episode_path = pipeline.run()
    print(f"Published episode: {episode_path}")
