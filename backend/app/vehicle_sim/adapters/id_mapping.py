UDP_TRAIN_SLOTS = 20

VEHICLE_ID_TO_INDEX = {
    f"TRAIN-{index:03d}": index for index in range(1, UDP_TRAIN_SLOTS + 1)
}

INDEX_TO_VEHICLE_ID = {
    index: vehicle_id for vehicle_id, index in VEHICLE_ID_TO_INDEX.items()
}


def vehicle_id_to_index(vehicle_id: str) -> int:
    if vehicle_id in VEHICLE_ID_TO_INDEX:
        return VEHICLE_ID_TO_INDEX[vehicle_id]

    prefix = "TRAIN-"
    if vehicle_id.startswith(prefix):
        try:
            index = int(vehicle_id.removeprefix(prefix))
        except ValueError:
            index = 0
        if index >= 1:
            return index

    raise ValueError(f"Unknown vehicle_id: {vehicle_id}")


def index_to_vehicle_id(train_index: int) -> str:
    if train_index in INDEX_TO_VEHICLE_ID:
        return INDEX_TO_VEHICLE_ID[train_index]

    if train_index >= 1:
        return f"TRAIN-{train_index:03d}"

    raise ValueError(f"train_index must be >= 1: {train_index}")

