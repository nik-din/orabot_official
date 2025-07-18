from typing import TypedDict


class Random(TypedDict):
    server_id: int
    randoms: list[str]

class OracoinUser(TypedDict):
    username: str
    oracoins: int
    locked_points:int
    last_daily_claim: int

class Oracoin(TypedDict):
    server_id: int 
    data: dict[str,OracoinUser ]


class Bet(TypedDict):
    user_id:int
    option_id: int
    amount: int 
    quotes: int

class Poll(TypedDict):
    creator_id:int 
    creator_username:str 
    question:str 
    options: list[str]
    quotes: list[int]
    bets: list[Bet]
    

class Polymarket(TypedDict):
    server_id: int
    polls: dict[str,Poll]
