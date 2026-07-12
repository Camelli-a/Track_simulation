"""
ZMQ 消息总线客户端
统一封装 publish / subscribe，对上层屏蔽 ZMQ 细节

用法：
    bus = MessageBus()
    bus.start()

    # 发布
    bus.publish("train_state", {"vehicle_id": "TRAIN-001", "speed": 80})

    # 订阅
    def on_train_state(topic, data):
        print(f"收到 {topic}: {data}")
    bus.subscribe("train_state", on_train_state)

    bus.stop()
"""
import json
import time
import logging
import threading
from typing import Callable, Dict, List
import zmq

from app.core.config import settings

logger = logging.getLogger(__name__)


def encode_bus_frame(topic: str, data: dict, timestamp: float | None = None) -> str:
    """Encode the project's single-frame ``<topic> <json>`` wire format."""
    if not topic or " " in topic:
        raise ValueError("topic must be a non-empty token without spaces")
    message = {
        "topic": topic,
        "timestamp": time.time() if timestamp is None else float(timestamp),
        "data": data,
    }
    return f"{topic} {json.dumps(message, ensure_ascii=False)}"


def decode_bus_frame(frame: str) -> tuple[str, dict]:
    """Decode and validate one bus frame; the prefix is authoritative."""
    prefix_topic, separator, payload_text = frame.partition(" ")
    if not separator:
        raise ValueError("message bus frame is missing topic prefix")
    payload = json.loads(payload_text)
    envelope_topic = payload.get("topic")
    if envelope_topic != prefix_topic:
        raise ValueError("message bus topic prefix does not match JSON envelope")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("message bus data must be an object")
    return prefix_topic, payload


class MessageBus:
    """
    ZMQ 消息总线客户端
    
    消息格式（统一包装）：
    {
        "topic":     "train_state",         # 消息类型
        "timestamp": 1720000000.123,        # 发送时刻（秒，浮点）
        "data":      { ... }                # 业务数据，各模块自定义
    }
    """

    def __init__(
        self,
        pub_address: str = None,
        sub_address: str = None,
    ):
        """
        Args:
            pub_address: 发布端连接地址（即 Broker 的 XSUB 地址）
            sub_address: 订阅端连接地址（即 Broker 的 XPUB 地址）
        """
        self.pub_address = pub_address or settings.ZMQ_BROKER_BACKEND
        self.sub_address = sub_address or settings.ZMQ_BROKER_FRONTEND

        self.context: zmq.Context = None
        self._pub_socket: zmq.Socket = None
        self._sub_socket: zmq.Socket = None
        self._pub_lock = threading.Lock()

        # topic -> [callback, ...]
        self._handlers: Dict[str, List[Callable]] = {}

        self._sub_thread: threading.Thread = None
        self._running = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        """初始化 ZMQ 连接并启动订阅监听线程"""
        self.context = zmq.Context()

        # 发布 socket（连接到 Broker 的 XSUB 端）
        self._pub_socket = self.context.socket(zmq.PUB)
        self._pub_socket.connect(self.pub_address)
        logger.info(f"MessageBus publisher connected: {self.pub_address}")

        # 订阅 socket（连接到 Broker 的 XPUB 端）
        self._sub_socket = self.context.socket(zmq.SUB)
        self._sub_socket.connect(self.sub_address)
        logger.info(f"MessageBus subscriber connected: {self.sub_address}")

        # 短暂等待，让 ZMQ 连接稳定（避免第一条消息丢失）
        time.sleep(0.1)

        self._running = True
        self._sub_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
            name="MessageBus-sub"
        )
        self._sub_thread.start()

    def stop(self):
        """停止消息总线"""
        self._running = False
        if self._pub_socket:
            self._pub_socket.close()
        if self._sub_socket:
            self._sub_socket.close()
        if self.context:
            self.context.term()
        logger.info("MessageBus stopped")

    # ------------------------------------------------------------------
    # 发布
    # ------------------------------------------------------------------

    def publish(self, topic: str, data: dict):
        """
        向总线发布一条消息
        
        Args:
            topic: 消息类型（如 "train_state"）
            data:  业务数据字典
        """
        frame = encode_bus_frame(topic, data)

        with self._pub_lock:
            self._pub_socket.send_string(frame)

        logger.debug(f"Published [{topic}]: {frame[:120]}")

    # ------------------------------------------------------------------
    # 订阅
    # ------------------------------------------------------------------

    def subscribe(self, topic: str, handler: Callable[[str, dict], None]):
        """
        订阅某类消息
        
        Args:
            topic:   消息类型（如 "train_state"）
            handler: 回调函数，签名 f(topic: str, data: dict)
        """
        if topic not in self._handlers:
            self._handlers[topic] = []
            # 告诉 ZMQ 我要这个 topic 的消息
            self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
            logger.info(f"Subscribed to topic: {topic}")

        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable = None):
        """
        取消订阅
        
        Args:
            topic:   消息类型
            handler: 若为 None，则取消该 topic 的所有回调
        """
        if topic not in self._handlers:
            return
        if handler is None:
            self._handlers.pop(topic, None)
            self._sub_socket.setsockopt_string(zmq.UNSUBSCRIBE, topic)
        else:
            self._handlers[topic] = [h for h in self._handlers[topic] if h != handler]

    # ------------------------------------------------------------------
    # 接收循环（后台线程）
    # ------------------------------------------------------------------

    def _receive_loop(self):
        """后台线程：持续接收消息并分发给对应 handler"""
        logger.info("MessageBus receive loop started")
        poller = zmq.Poller()
        poller.register(self._sub_socket, zmq.POLLIN)

        while self._running:
            try:
                events = dict(poller.poll(timeout=200))  # 200ms 超时，便于检查 _running
                if self._sub_socket not in events:
                    continue

                frame = self._sub_socket.recv_string()

                topic, message = decode_bus_frame(frame)
                data = message.get("data", {})

                handlers = self._handlers.get(topic, [])
                for handler in handlers:
                    try:
                        handler(topic, data)
                    except Exception as e:
                        logger.error(f"Handler error [{topic}]: {e}", exc_info=True)

            except zmq.ZMQError as e:
                if self._running:
                    logger.error(f"ZMQ error in receive loop: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error in receive loop: {e}", exc_info=True)

        logger.info("MessageBus receive loop stopped")
