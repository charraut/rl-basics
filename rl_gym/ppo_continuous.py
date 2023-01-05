import argparse
import time
import random
from datetime import datetime
from warnings import simplefilter

import gymnasium as gym
import numpy as np
from tqdm import tqdm

import torch
from torch import optim, nn
from torch.nn.functional import mse_loss
from torch.nn.utils.clip_grad import clip_grad_norm_
from torch.distributions import Normal
from torch.utils.tensorboard.writer import SummaryWriter

simplefilter(action="ignore", category=DeprecationWarning)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=str, default="HalfCheetah-v4")
    parser.add_argument("--total-timesteps", type=int, default=int(1e6))
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--num-steps", type=int, default=2048)
    parser.add_argument("--num-minibatches", type=int, default=32)
    parser.add_argument("--num-optims", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument('--list-layer', nargs="+", type=int, default=[64, 64])
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--gae", type=float, default=0.95)
    parser.add_argument("--eps-clip", type=float, default=0.2)
    parser.add_argument("--value-factor", type=float, default=0.5)
    parser.add_argument("--entropy-factor", type=float, default=0.01)
    parser.add_argument("--shared-network", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--capture-video", action="store_true")
    parser.add_argument("--seed", type=int, default=0)

    _args = parser.parse_args()

    _args.device = torch.device(
        "cpu" if _args.cpu or not torch.cuda.is_available() else "cuda")
    _args.batch_size = int(_args.num_envs * _args.num_steps)
    _args.minibatch_size = int(_args.batch_size // _args.num_minibatches)
    _args.num_updates = int(_args.total_timesteps // _args.num_steps)

    return _args


def make_env(env_id, idx, run_name, capture_video):

    def thunk():

        if capture_video:
            env = gym.make(env_id, render_mode="rgb_array")
        else:
            env = gym.make(env_id)
        env = gym.wrappers.RecordEpisodeStatistics(env)
        env = gym.wrappers.ClipAction(env)
        env = gym.wrappers.FlattenObservation(env)
        env = gym.wrappers.NormalizeObservation(env)
        env = gym.wrappers.TransformObservation(
            env, lambda obs: np.clip(obs, -10, 10))
        env = gym.wrappers.NormalizeReward(env, gamma=0.99)
        env = gym.wrappers.TransformReward(
            env, lambda reward: np.clip(reward, -10, 10))
        if capture_video and idx == 0:
            env = gym.wrappers.RecordVideo(
                env=env,
                video_folder=f"runs/{run_name}/videos/",
                disable_logger=True)
        return env

    return thunk


def layer_init(layer, std=np.sqrt(2), bias_const=0.):

    torch.nn.init.orthogonal_(layer.weight, std)
    torch.nn.init.constant_(layer.bias, bias_const)
    return layer


class Agent(nn.Module):

    def __init__(self, args, obversation_space, action_space):

        super().__init__()

        current_layer_value = np.array(obversation_space.shape).prod()
        num_actions = np.array(action_space.shape).prod()

        if args.shared_network:
            base_neural_net = nn.Sequential()

            for layer_value in args.list_layer:
                base_neural_net.append(
                    layer_init(nn.Linear(current_layer_value, layer_value)))
                base_neural_net.append(nn.Tanh())

                current_layer_value = layer_value

            self.actor_neural_net = nn.Sequential(
                base_neural_net,
                layer_init(nn.Linear(args.list_layer[-1], num_actions),
                           std=0.01))

            self.critic_neural_net = nn.Sequential(
                base_neural_net,
                layer_init(nn.Linear(args.list_layer[-1], 1), std=1.))

        else:
            self.actor_neural_net = nn.Sequential()
            self.critic_neural_net = nn.Sequential()

            for layer_value in args.list_layer:
                self.actor_neural_net.append(
                    layer_init(nn.Linear(current_layer_value, layer_value)))
                self.actor_neural_net.append(nn.Tanh())

                self.critic_neural_net.append(
                    layer_init(nn.Linear(current_layer_value, layer_value)))
                self.critic_neural_net.append(nn.Tanh())

                current_layer_value = layer_value

            self.actor_neural_net.append(
                layer_init(nn.Linear(args.list_layer[-1], num_actions),
                           std=0.01))

            self.critic_neural_net.append(
                layer_init(nn.Linear(args.list_layer[-1], 1), std=1.))

        self.optimizer = optim.Adam(self.parameters(), lr=args.learning_rate)

        self.actor_logstd = nn.Parameter(torch.zeros(1, num_actions))

        if args.device.type == "cuda":
            self.cuda()

    def forward(self):
        pass

    def get_action_value(self, state, action=None):

        action_mean = self.actor_neural_net(state)
        action_std = self.actor_logstd.expand_as(action_mean).exp()
        distribution = Normal(action_mean, action_std)

        if action is None:
            action = distribution.sample()

        log_prob = distribution.log_prob(action).sum(-1)
        dist_entropy = distribution.entropy().sum(-1)

        critic_value = self.critic_neural_net(state).squeeze()

        return action.cpu().numpy(), log_prob, critic_value, dist_entropy

    def get_value(self, state):

        return self.critic_neural_net(state)


def main():
    args = parse_args()

    date = str(datetime.now().strftime("%d-%m_%H:%M:%S"))
    run_name = f"{args.env}__ppo__{date}"
    writer = SummaryWriter(f"runs/{run_name}")
    writer.add_text(
        "hyperparameters",
        "|param|value|\n|-|-|\n%s" %
        ("\n".join([f"|{key}|{value}|" for key, value in vars(args).items()])),
    )

    if args.seed > 0:
        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)

    # Create vectorized environment(s)
    envs = gym.vector.SyncVectorEnv([
        make_env(args.env, i, run_name, args.capture_video)
        for i in range(args.num_envs)
    ])

    obversation_space = envs.single_observation_space
    action_space = envs.single_action_space

    agent = Agent(args, obversation_space, action_space)

    obversation_shape = obversation_space.shape
    action_shape = action_space.shape

    states = torch.zeros((args.num_steps, args.num_envs) +
                         obversation_shape).to(args.device)
    actions = torch.zeros((args.num_steps, args.num_envs) + action_shape).to(
        args.device)
    rewards = torch.zeros((args.num_steps, args.num_envs)).to(args.device)
    flags = torch.zeros((args.num_steps, args.num_envs)).to(args.device)
    log_probs = torch.zeros((args.num_steps, args.num_envs)).to(args.device)
    state_values = torch.zeros((args.num_steps, args.num_envs)).to(args.device)

    if args.seed > 0:
        state, _ = envs.reset(seed=args.seed)
    else:
        state, _ = envs.reset()

    global_step = 0

    for update in tqdm(range(args.num_updates)):
        start = time.perf_counter()

        # Annealing learning rate
        frac = 1. - (update - 1.) / args.num_updates
        new_lr = frac * args.learning_rate
        agent.optimizer.param_groups[0]["lr"] = new_lr

        # Generate transitions
        for i in range(args.num_steps):
            global_step += 1

            with torch.no_grad():
                state_torch = torch.from_numpy(state).to(args.device).float()
                action, log_prob, state_value, _ = agent.get_action_value(
                    state_torch)

            next_state, reward, terminated, truncated, infos = envs.step(
                action)

            states[i] = state_torch
            actions[i] = torch.from_numpy(action).to(args.device)
            rewards[i] = torch.from_numpy(reward).to(args.device)
            log_probs[i] = log_prob
            state_values[i] = state_value

            done = np.logical_or(terminated, truncated)
            flags[i] = torch.from_numpy(done).to(args.device)

            state = next_state

            if "final_info" not in infos:
                continue

            for info in infos["final_info"]:
                if info is None:
                    continue

                writer.add_scalar("rollout/episodic_return",
                                  info["episode"]["r"], global_step)
                writer.add_scalar("rollout/episodic_length",
                                  info["episode"]["l"], global_step)

        end = time.perf_counter()
        writer.add_scalar("rollout/time", end - start, global_step)

        # Compute values
        with torch.no_grad():
            state_torch = torch.from_numpy(state).to(args.device).float()
            next_state_value = agent.get_value(state_torch).squeeze(-1)

        advantages = torch.zeros(rewards.size()).to(args.device)
        adv = torch.zeros(rewards.size(1)).to(args.device)

        for i in reversed(range(rewards.size(0))):
            terminal = 1. - flags[i]

            returns = rewards[i] + args.gamma * next_state_value * terminal
            delta = returns - state_values[i]

            adv = args.gamma * args.gae * adv * terminal + delta
            advantages[i] = adv

            next_state_value = state_values[i]

        td_target = (advantages + state_values).squeeze()
        advantages = (advantages - advantages.mean()) / (advantages.std() +
                                                         1e-7)
        advantages = advantages.squeeze()

        # Flatten batch
        _states = states.flatten(0, 1)
        _actions = actions.flatten(0, 1)
        _log_probs = log_probs.reshape(-1)
        _td_target = td_target.reshape(-1)
        _advantages = advantages.reshape(-1)

        batch_indexes = np.arange(args.batch_size)

        clipfracs = []

        # Update policy
        for _ in range(args.num_optims):

            # Shuffle batch
            np.random.shuffle(batch_indexes)

            for start in range(0, args.batch_size, args.minibatch_size):
                end = start + args.minibatch_size
                index = batch_indexes[start:end]

                _, new_log_probs, td_predict, dist_entropy = agent.get_action_value(
                    _states[index], _actions[index])

                logratio = new_log_probs - _log_probs[index]
                ratios = logratio.exp()

                with torch.no_grad():
                    # Calculate approx_kl http://joschu.net/blog/kl-approx.html
                    old_approx_kl = (-logratio).mean()
                    approx_kl = ((ratios - 1) - logratio).mean()
                    clipfracs += [
                        ((ratios - 1.).abs() > 0.2).float().mean().item()
                    ]

                surr1 = _advantages[index] * ratios

                surr2 = _advantages[index] * torch.clamp(
                    ratios, 1. - args.eps_clip, 1. + args.eps_clip)

                policy_loss = -torch.min(surr1, surr2).mean()

                value_loss = args.value_factor * mse_loss(
                    td_predict, _td_target[index])

                entropy_bonus = args.entropy_factor * dist_entropy.mean()

                loss = policy_loss + value_loss - entropy_bonus

                agent.optimizer.zero_grad()
                loss.backward()
                clip_grad_norm_(agent.parameters(), 0.5)
                agent.optimizer.step()

        writer.add_scalar("update/policy_loss", policy_loss, global_step)
        writer.add_scalar("update/value_loss", value_loss, global_step)
        writer.add_scalar("debug/old_approx_kl", old_approx_kl, global_step)
        writer.add_scalar("debug/approx_kl", approx_kl, global_step)
        writer.add_scalar("debug/clipfrac", np.mean(clipfracs), global_step)

    envs.close()
    writer.close()


if __name__ == '__main__':
    main()