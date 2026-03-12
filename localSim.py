import json

from riichienv import RiichiEnv

from .ukeire_agent import UkeMaxAgent


def main():
    # Seed here controls only this agent's randomness
    agent = UkeMaxAgent(seed=42)
    # Create a game environment
    #   game_mode: 1 = East-only, 2 = East-South (hanchan)
    #   seed: fixed seed for reproducibility (optional)
    env = RiichiEnv(game_mode=2, seed=42)
    # Get initial observations for all players
    observations = env.get_observations()
    print("observations", observations)
    while not env.done():
        # Find the player who needs to act
        for pid, obs in observations.items():
            actions = obs.legal_actions()
            if actions:
                # Your agent decides the action
                action = agent.act(obs)
                if action is None:
                    continue
                # Environment expects a dict of {player_id: action}
                observations = env.step({pid: action})
                break
    # Game finished — check results
    print("Scores:", env.scores())
    print("Ranks:", env.ranks())
    # Full MJAI log is available
    for event in env.mjai_log:
        print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    main()