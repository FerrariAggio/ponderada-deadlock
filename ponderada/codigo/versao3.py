"""CC08 V3: produtor adquire mutex antes de vazio, expondo um deadlock."""

from experimento import main

if __name__ == "__main__":
    main(3)
