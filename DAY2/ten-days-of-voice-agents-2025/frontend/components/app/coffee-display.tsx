'use client';

import { useEffect, useState } from 'react';
import { useRoomContext } from '@livekit/components-react';
import { RoomEvent } from 'livekit-client';
import { motion, AnimatePresence } from 'motion/react';

interface OrderState {
    drinkType: string;
    size: string;
    milk: string;
    extras: string[];
}

export function CoffeeDisplay() {
    const room = useRoomContext();
    const [order, setOrder] = useState<OrderState | null>(null);

    useEffect(() => {
        const onData = (payload: Uint8Array, participant: any, _kind: any, topic?: string) => {
            if (topic === 'order_update') {
                try {
                    const str = new TextDecoder().decode(payload);
                    const data = JSON.parse(str);
                    setOrder(data);
                } catch (e) {
                    console.error('Failed to parse order update:', e);
                }
            }
        };

        room.on(RoomEvent.DataReceived, onData);
        return () => {
            room.off(RoomEvent.DataReceived, onData);
        };
    }, [room]);

    if (!order) {
        return null;
    }

    // Determine visual properties based on order
    const getSizeScale = (size: string) => {
        switch (size?.toLowerCase()) {
            case 'small': return 0.8;
            case 'large': return 1.2;
            default: return 1.0; // Medium
        }
    };

    const getDrinkColor = (type: string) => {
        const t = type?.toLowerCase() || '';
        if (t.includes('latte')) return '#C4A484'; // Light brown
        if (t.includes('cappuccino')) return '#8D6E63'; // Medium brown
        if (t.includes('americano')) return '#3E2723'; // Dark brown
        if (t.includes('espresso')) return '#212121'; // Almost black
        if (t.includes('mocha')) return '#5D4037'; // Chocolatey
        if (t.includes('matcha')) return '#81C784'; // Green
        return '#6D4C41'; // Default coffee color
    };

    const hasWhippedCream = order.extras?.some(e => e.toLowerCase().includes('whipped'));
    const scale = getSizeScale(order.size);
    const color = getDrinkColor(order.drinkType);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="absolute top-24 right-4 z-50 w-64 rounded-xl border border-white/10 bg-black/40 p-4 backdrop-blur-md shadow-xl"
        >
            <h3 className="mb-4 text-center text-sm font-medium text-white/80 uppercase tracking-wider">
                Current Order
            </h3>

            <div className="flex h-48 items-center justify-center">
                <div className="relative transition-all duration-500 ease-spring" style={{ transform: `scale(${scale})` }}>
                    {/* Cup Handle */}
                    <div className="absolute right-[-15px] top-4 h-16 w-8 rounded-r-xl border-4 border-l-0 border-white/80" />

                    {/* Cup Body */}
                    <div className="relative h-32 w-24 overflow-hidden rounded-b-3xl rounded-t-sm bg-white/90 shadow-inner">
                        {/* Coffee Liquid */}
                        <div
                            className="absolute bottom-0 left-0 right-0 transition-colors duration-500"
                            style={{
                                height: '85%',
                                backgroundColor: color,
                            }}
                        />

                        {/* Whipped Cream */}
                        <AnimatePresence>
                            {hasWhippedCream && (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0 }}
                                    className="absolute top-[10%] left-1/2 -translate-x-1/2 -translate-y-1/2"
                                >
                                    <div className="flex flex-col items-center">
                                        <div className="h-6 w-16 rounded-full bg-white shadow-sm" />
                                        <div className="h-6 w-12 -mt-3 rounded-full bg-white shadow-sm" />
                                        <div className="h-4 w-6 -mt-3 rounded-full bg-white shadow-sm" />
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Cup Rim */}
                    <div className="absolute top-0 h-2 w-24 rounded-full bg-gray-200" />
                </div>
            </div>

            <div className="mt-4 space-y-1 text-center">
                <div className="text-lg font-bold text-white">
                    {order.size} {order.drinkType}
                </div>
                {order.milk && order.milk !== 'None' && (
                    <div className="text-xs text-white/60">
                        with {order.milk} Milk
                    </div>
                )}
                {order.extras && order.extras.length > 0 && (
                    <div className="flex flex-wrap justify-center gap-1 pt-1">
                        {order.extras.map((extra, i) => (
                            <span key={i} className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/80">
                                {extra}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </motion.div>
    );
}
