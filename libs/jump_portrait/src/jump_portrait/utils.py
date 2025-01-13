"""General utilities."""

from collections.abc import Callable, Iterable
from itertools import chain
from typing import Any

from joblib import Parallel, cpu_count, delayed
from tqdm import tqdm


def slice_iterable(iterable: Iterable[Any], count: int) -> list[slice]:
    """
    Create slices of the given iterable.

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
    verbose: bool = True,
    **kwargs: dict[Any, Any],
) -> list[Any]:
    """
    Distribute process on iterable.

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
    verbose: bool, optional
        Whether to enable tqdm or not.
    *args
        Additional arguments.
        They additional arguments are passed to `func`.
    **kwargs
        Additional parameters for your function.
        They keyword arguments are passed to `func`.

    Returns
    -------
    list[Any]
        A list of outputs genetated by function.

    Notes
    -----
    `kwargs` are passed as

    """
    jobs = jobs or cpu_count()

    if not hasattr(iterable, "__len__"):
        iterable = list(iterable)

    if len(iterable) < jobs:
        jobs = len(iterable)
    slices = slice_iterable(iterable, jobs)
    result = Parallel(n_jobs=jobs, timeout=timeout)(
        delayed(func)(chunk, idx, verbose, *args, **kwargs)
        for idx, chunk in enumerate([iterable[s] for s in slices])
    )

    if result is not None:
        return list(chain(*[x for x in result if x is not None]))


def batch_processing(fn: Callable) -> Callable:
    """
    Decorate a function for parallel batch processing.

    Parameters
    ----------
    fn: Callable
        Function to be wrapped for batch processing.

    Returns
    -------
    batched_fn : Wrapped function that contains job id information.

    """
    # This assumes parameters are packed in a tuple
    def batched_fn(
        item_list: Iterable,
        job_idx: int,
        verbose: bool = True,
        *args: Iterable,
        **kwargs: dict,
    ) -> list:
        """
        Process a list of items in batches.

        Parameters
        ----------
        item_list : Iterable
            List of items to be processed.
        job_idx : int
            Index of the current job.
        verbose : bool, optional
            Whether to display progress bar (default is True).
        *args :
            Additional positional arguments to be passed to the function f.
        **kwargs :
            Additional keyword arguments to be passed to the function f.

        Returns
        -------
        list
            List of results if any item in the list is not None, otherwise None.

        """
        results = []
        for item in tqdm(
            item_list,
            position=0,
            leave=True,
            disable=not verbose,
            desc=f"worker #{job_idx}",
        ):
            results.append(fn(*item, *args, **kwargs))

        if any([x is not None for x in results]):
            return results

    return batched_fn


def try_function(fn: Callable) -> Callable:
    """
    Wrap a function into an instance which will Try to call the function.

    If it success, return the output of the function.
    If it fails, return None.

    Parameters
    ----------
    fn : Callable
        Function to wrap inside a try-except block.

    Returns
    -------
    tried_fn : Callable
        Wrapped function.

    """

    # This assumes parameters are packed in a tuple
    def try_exc_block(*item: Iterable, **kwargs:dict) -> any:
        """
        Execute a function with exception handling.

        Parameters
        ----------
        f : callable
            The function to be executed.
        *item : Iterable
            Variable length argument list for the function f.
        **kwargs : dict
            Arbitrary keyword arguments for the function f.

        Returns
        -------
        result : any
            Result of the function execution, or None if an exception occurs.

        Notes
        -----
        This function wraps a given function with a try-except block to handle exceptions.
        If an exception occurs during the function execution, it returns None.

        """
        try:
            result = fn(*item, **kwargs)
        except Exception as e:
            print(f"An error occurred: {e}")
            result = None
        return result

    return try_exc_block
