#!/usr/bin/env jupyter
import jax.numpy as jnp
from jax.random import PRNGKey, uniform

key = PRNGKey(1)
n_iter = 50
dt = 0.1
n_observed = 2

# "Observations"

X = jnp.array([[0], [0], [0.1], [0.1]])
Ys = jnp.cumsum(uniform(key, (n_iter, n_observed)), axis=0)
P = jnp.eye(len(X)) * 0.1
A = jnp.array(
    [
        [1, 0, dt, 0],
        [0, 1, 0, dt],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ]
)
# Measurement matrices

# Constants
Q = jnp.eye(len(X))
B = jnp.eye(len(X))
U = jnp.zeros((len(X), 1))
H = jnp.array(
    [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
    ]
)
R = jnp.eye(Ys.shape[1])


def kf_predict(X, P, A, Q, B, U):
    X = jnp.dot(A, X) + jnp.dot(B, U)
    P = jnp.dot(A, jnp.dot(P, A.T)) + Q

    return X, P


def kf_update(X, P, Y, H, R):
    IM = jnp.dot(H, X)
    IS = R + jnp.dot(H, jnp.dot(P, H.T))
    K = jnp.dot(P, jnp.dot(H.T, jnp.linalg.inv(IS)))
    X = X + jnp.dot(K, (Y - IM))
    P = P - jnp.dot(K, jnp.dot(IS, K.T))
    return (X, P, K, IM, IS)


def apply_kalman_iteration(X, P, K, IM, IS, Y):
    X, P = kf_predict(X, P, A, Q, B, U)
    X, P, K, IM, IS = kf_update(X, P, Y, H, R)
    return X, P, K, IM, IS


a = []
for Y in Ys:
    X, P = kf_predict(X, P, A, Q, B, U)
    X, P, K, IM, IS = kf_update(X, P, Y, H, R)
    a.append(X)
