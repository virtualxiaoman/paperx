from paperx.models import BBox


def unrotate_bbox(box: tuple[float, float, float, float], rotation: int) -> BBox:
    """Display normalized x0/y0/x1/y1 -> original unrotated normalized bbox."""

    def inverse(x: float, y: float):
        match rotation:
            case 0:
                return x, y
            case 90:
                return y, 1 - x
            case 180:
                return 1 - x, 1 - y
            case 270:
                return 1 - y, x
            case _:
                raise ValueError("rotation must be a quarter turn")

    x0, y0, x1, y1 = box
    points = [inverse(x, y) for x in (x0, x1) for y in (y0, y1)]
    xs, ys = zip(*points)
    left, top = max(0, min(xs)), max(0, min(ys))
    right, bottom = min(1, max(xs)), min(1, max(ys))
    return BBox(x=left, y=top, width=right - left, height=bottom - top)
