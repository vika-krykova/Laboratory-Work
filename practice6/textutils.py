import re
from functools import lru_cache

STOP_RU = set("""и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне
было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь
опять уж вам сказал ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам
чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один
почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над
больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда
лучше чуть том нельзя такой им более всегда конечно всю между это просто вообще очень типа короче значит
например который которые которая которое также свой наш ваш такие такое такая именно потом сразу еще""".split())

_WORD = re.compile(r"[a-zа-я0-9]+", re.I)
_morph = None
_morph_tried = False


def _get_morph():
    global _morph, _morph_tried
    if not _morph_tried:
        _morph_tried = True
        try:
            import pymorphy3
            _morph = pymorphy3.MorphAnalyzer()
        except Exception:
            _morph = None
    return _morph


def has_lemmatizer():
    return _get_morph() is not None


@lru_cache(maxsize=200000)
def _norm_word(w):
    m = _get_morph()
    if m is not None and re.search("[а-я]", w):
        return m.parse(w)[0].normal_form.replace("ё", "е")
    return w if len(w) <= 5 else w[:5]


def normalize(text, min_len=3):
    out = []
    for w in _WORD.findall((text or "").lower().replace("ё", "е")):
        if len(w) < min_len or w.isdigit() or w in STOP_RU:
            continue
        lem = _norm_word(w)
        if lem not in STOP_RU:
            out.append(lem)
    return out
