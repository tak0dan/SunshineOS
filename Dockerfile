FROM archlinux:latest
RUN pacman-key --init && pacman-key --populate archlinux && \
    pacman -Syu --noconfirm archiso git base-devel sudo && pacman -Scc --noconfirm
