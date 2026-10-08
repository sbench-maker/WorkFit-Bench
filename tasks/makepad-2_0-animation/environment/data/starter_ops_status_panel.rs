use makepad_widgets::*;

script_mod! {
    use mod.prelude.widgets.*

    // BUG: Label does not own a working Animator in Makepad 2.0.
    let StatusCard = Label{
        width: Fill height: 56
        padding: 14
        text: "Indexing local workspace"
        draw_text.color: #e8ecf8
        animator: Animator{
            hover: {
                default: @off
                off: AnimatorState{
                    from: {all: Forward {duration: 0.18}}
                    ease: OutCubic
                    apply: {draw_bg: {hover: 0.0}}
                }
                on: AnimatorState{
                    from: {all: Forward {duration: 0.18}}
                    ease: OutCubic
                    apply: {draw_bg: {hover: 1.0}}
                }
            }
        }
    }

    let SyncSpinner = View{
        width: 24 height: 24
        draw_bg +: {
            rotation: uniform(0.0)
            pixel: fn() {
                let sdf = Sdf2d.viewport(self.pos * self.rect_size)
                let cx = self.rect_size.x * 0.5
                let cy = self.rect_size.y * 0.5
                let r = min(cx, cy) * 0.72
                sdf.arc(cx, cy, r, self.rotation, self.rotation + 4.5, 2.5)
                sdf.stroke(#72a7ff, 2.5)
                return sdf.result
            }
        }
        // BUG: this initializes off and only moves forward once.
        animator: Animator{
            time: {
                default: @off
                off: AnimatorState{
                    from: {all: Snap}
                    apply: {draw_bg: {rotation: 0.0}}
                }
                on: AnimatorState{
                    from: {all: Forward {duration: 1.2}}
                    apply: {draw_bg: {rotation: 6.28318}}
                }
            }
        }
    }

    let OpsStatusPanel = RoundedView{
        width: Fill height: Fit
        flow: Right
        spacing: 12
        padding: 16
        draw_bg.color: #151a28

        status_card := StatusCard{}
        sync_spinner := SyncSpinner{}
    }
}
