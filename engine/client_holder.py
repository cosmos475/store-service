bot = None


def set_bot(instance) -> None:
    global bot
    bot = instance


def get_bot():
    return bot
