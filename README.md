# RL-Gym

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

The goal of this repository is to implement any RL algorithms and try to benchmarks them in the [Gymnasium](https://github.com/Farama-Foundation/Gymnasium) framework.  
Made in Python (3.10) with [Pytorch](https://github.com/pytorch/pytorch).

| RL Algorithm            | Discrete | Continuous |
|-------------------------|:--------:|:----------:|
| A2C [[1]](#references)  |     X    |      X     |
| PPO [[2]](#references)  |     X    |      X     |
| DDPG [[3]](#references) |          |            |
| TD3 [[4]](#references)  |          |            |
| SAC [[5]](#references)  |          |            |

| Gymnasium Environments                                                               | Supported |
|--------------------------------------------------------------------------------------|:---------:|
| [Classic Control](https://gymnasium.farama.org/environments/classic_control/)        |     X     |
| [Box2D](https://gymnasium.farama.org/environments/box2d/)                            |     X     |
| [Toy Text](https://gymnasium.farama.org/environments/toy_text/)                      |     X     |
| [MuJoCo](https://gymnasium.farama.org/environments/mujoco/)                          |     X     |
| [Atari](https://gymnasium.farama.org/environments/atari/)                            |     X     |
---

## Setup

Clone the code repo and install the requirements.

```
git clone https://github.com/valentin-cnt/rl-gym.git
cd rl-gym

poetry install
```

---

## Run

---

## Results

---

## Acknowledgments

 - [CleanRL](https://github.com/vwxyzjn/cleanrl)

## References

- [1] [Asynchronous Methods for Deep Reinforcement Learning](https://arxiv.org/abs/1602.01783)
- [2] [Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347)
- [3] [Deterministic Policy Gradient Algorithms](https://proceedings.mlr.press/v32/silver14.pdf)
- [4] [Addressing Function Approximation Error in Actor-Critic Methods](https://arxiv.org/abs/1802.09477)
- [5] [Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor](https://arxiv.org/abs/1801.01290)
