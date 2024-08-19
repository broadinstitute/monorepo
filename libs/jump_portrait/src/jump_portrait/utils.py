"""General utilities"""

from collections.abc import Callable, Iterable
from itertools import chain
from typing import Any

from joblib import Parallel, cpu_count, delayed
from tqdm import tqdm

def slice_iterable(iterable: Iterable[Any], count: int) -> list[slice]:
    """Create slices of the given iterable.

    Parameters
    ----------
    iterable : Iterable[Any]
        A iterable to create slices.
    count : int
        Number of slices to create.

    Returns
    -------
    list[slice]
        A list of slice.
    """
    slices = []
    if count == 0:
        slices.append(slice(0, len(iterable)))
        return slices
    if len(iterable) < count:
        raise Exception(
            f"Length of iterable: {len(iterable)} is less than count: {count}"
        )
    for i in range(0, len(iterable), len(iterable) // count):
        slices.append(slice(i, i + len(iterable) // count))
    return slices


def parallel(
    iterable: Iterable[Any],
    func: Callable[[list[Any], Any], Any],
    args: list[Any] = [],
    jobs: int = None,
    timeout: float = None,
    print_progress: bool = True,
    **kwargs: dict[Any, Any],
) -> list[Any]:
    """Distribute process on iterable.

    Parameters
    ----------
    iterable : Iterable[Any]
        Iterable to chunk and distribute.
    func : Callable[[list[Any], Any], Any]
        Function to distribute.
    args : list[Any], optional
        Optional addtional args for the function, by default []
    jobs : int, optional
        Number of jobs to launch, by default None
    timeout: float, optional
        Timeout for worker processes.
    print_progress: bool, optional
        Whether to enable tqdm or not.

    Returns
    -------
    list[Any]
        A list of outputs genetated by function.
    """
    jobs = jobs or cpu_count()

    if not hasattr(iterable, "__len__"):
        iterable = list(iterable)

    if len(iterable) < jobs:
        jobs = len(iterable)
    slices = slice_iterable(iterable, jobs)
    result = Parallel(n_jobs=jobs, timeout=timeout)(
        delayed(func)(chunk, idx, print_progress, *args, **kwargs)
        for idx, chunk in enumerate([iterable[s] for s in slices])
    )

    if result is not None:
        return list(chain(*[x for x in result if x is not None]))


def batch_processing(f: Callable):
    # This assumes parameters are packed in a tuple
    def batched_fn(item_list: Iterable, job_idx: int,
                   print_progress:bool=True,
                   *args, **kwargs):
        results = []
        for item in tqdm(item_list, position=0, leave=True,
                         disable=not print_progress,
                         desc=f"worker #{job_idx}"):
            results.append(f(*item, *args, **kwargs))

        if any([x is not None for x in results]):
            return results

    return batched_fn


def try_function(f: Callable):
    '''
    Wrap a function into an instance which will Try to call the function:
        If it success, return a tuple of function parameters + its results
        If it fails, return the function parameters
    '''
    # This assume parameters are packed in a tuple
    def batched_fn(*item, **kwargs):
        try:
            result = (*item, f(*item, **kwargs))

        except:
            result = item

        return result
    return batched_fn
