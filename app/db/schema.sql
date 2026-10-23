CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_type TEXT NOT NULL,           -- 'gomoku' / 'xiangqi'
    model_name TEXT,
    difficulty TEXT,
    user_color TEXT NOT NULL,
    result TEXT DEFAULT 'ongoing',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    move_number INTEGER NOT NULL,
    player TEXT NOT NULL,              -- 'user' / 'ai'
    position TEXT NOT NULL,            -- 五子棋 'row,col' / 象棋 ICCS 'h2e2'
    llm_commentary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_moves_game ON moves(game_id);
