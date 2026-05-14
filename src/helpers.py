def get_next_message(local=True):

    if local:
        return input("You: ").strip()
    else:
        # webhook
        pass
